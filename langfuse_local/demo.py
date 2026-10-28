"""Send a small, entirely local RAG simulation to Langfuse and verify ingestion.

Run: .venv/bin/python demo.py
No real model is called. Token counts are synthetic demo data.
"""

import argparse
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from langfuse import Langfuse, propagate_attributes

HERE = Path(__file__).resolve().parent


def make_client() -> Langfuse:
    load_dotenv(HERE / ".env")
    # Avoid sending localhost traffic through a system HTTP proxy.
    return Langfuse(
        public_key=os.environ["LANGFUSE_INIT_PROJECT_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_INIT_PROJECT_SECRET_KEY"],
        base_url=os.environ.get("LANGFUSE_BASE_URL", "http://localhost:3000"),
        environment="local-demo",
        httpx_client=httpx.Client(trust_env=False, timeout=30),
    )


def run_case(client: Langfuse, run_id: str, scenario: str) -> dict:
    question = "Langfuse 可以观测哪些信息？"
    started = time.perf_counter()
    with propagate_attributes(
        user_id="demo-user",
        session_id=run_id,
        trace_name=f"demo-rag-{scenario}",
        tags=["wsl", "demo", "simulated", scenario],
        metadata={"run_id": run_id, "mode": "simulation"},
    ):
        with client.start_as_current_observation(
            name=f"demo-rag-{scenario}",
            as_type="chain",
            input={"question": question, "scenario": scenario},
            metadata={"simulated": True},
        ) as root:
            trace_id = root.trace_id
            with client.start_as_current_observation(
                name="retrieve-documents",
                as_type="retriever",
                input={"query": question, "top_k": 1},
            ) as retrieval:
                time.sleep(0.08)
                documents = [] if scenario == "retrieval-error" else [
                    {"id": "doc-1", "text": "Langfuse 记录输入、输出、耗时、模型调用、token 用量及评分。"}
                ]
                retrieval.update(output={"documents": documents})
                if not documents:
                    retrieval.update(level="ERROR", status_message="Demo: no documents found")

            if not documents:
                answer = None
                root.update(
                    level="ERROR",
                    status_message="Demo: retrieval returned no documents",
                    output={"error": "No documents found", "answer": None},
                )
                client.create_score(
                    trace_id=trace_id,
                    name="answer_contains_expected_fact",
                    value=0,
                    data_type="BOOLEAN",
                    comment="Intentional demo failure: retrieval was empty.",
                )
            else:
                with client.start_as_current_observation(
                    name="simulated-llm-answer",
                    as_type="generation",
                    model="demo-model-simulated",
                    model_parameters={"temperature": 0},
                    input=[
                        {"role": "system", "content": documents[0]["text"]},
                        {"role": "user", "content": question},
                    ],
                    metadata={"simulated": True, "token_counts": "synthetic"},
                ) as generation:
                    time.sleep(0.8 if scenario == "slow-generation" else 0.12)
                    answer = "Langfuse 可以观测输入、输出、耗时、嵌套模型调用、token 用量和评分。"
                    generation.update(output=answer, usage_details={"input": 32, "output": 28})

                with client.start_as_current_observation(
                    name="evaluate-answer",
                    as_type="evaluator",
                    input={"answer": answer, "expected_keyword": "耗时"},
                ) as evaluation:
                    passed = "耗时" in answer
                    evaluation.update(output={"passed": passed})
                    client.create_score(
                        trace_id=trace_id,
                        name="answer_contains_expected_fact",
                        value=int(passed),
                        data_type="BOOLEAN",
                        comment="Local keyword check; no judge model involved.",
                    )
                root.update(output={"answer": answer})

    return {
        "scenario": scenario,
        "trace_id": trace_id,
        "trace_url": client.get_trace_url(trace_id=trace_id),
        "expected_observations": 2 if scenario == "retrieval-error" else 4,
        "expected_score": 0 if scenario == "retrieval-error" else 1,
        "answer": answer,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def verify(client: Langfuse, results: list[dict], timeout: float) -> list[dict]:
    """Poll the public API until worker ingestion and scoring finish."""
    deadline = time.monotonic() + timeout
    verified = {}
    errors = {}
    while time.monotonic() < deadline:
        for result in results:
            trace_id = result["trace_id"]
            if trace_id in verified:
                continue
            try:
                observations = client.api.observations.get_many(
                    trace_id=trace_id,
                    fields="core,basic,usage,io",
                    limit=100,
                ).data
                scores = client.api.scores_v3.get_many_v3(
                    trace_id=trace_id,
                    name="answer_contains_expected_fact",
                    limit=100,
                ).data
                assert len(observations) == result["expected_observations"], "Observations still ingesting"
                assert len(scores) == 1 and scores[0].value == result["expected_score"], "Score not ingested"
                roots = [o for o in observations if o.parent_observation_id is None]
                assert len(roots) == 1, "Expected one root observation"
                assert all(
                    o.parent_observation_id == roots[0].id
                    for o in observations if o.id != roots[0].id
                ), "Incorrect observation nesting"
                if result["scenario"] == "retrieval-error":
                    assert roots[0].level == "ERROR", "Missing expected error status"
                else:
                    generation = next(o for o in observations if o.type == "GENERATION")
                    assert generation.usage_details["input"] == 32
                    assert generation.usage_details["output"] == 28
                    assert generation.output == result["answer"], "Incorrect generation output"
                verified[trace_id] = {
                    **result,
                    "verified": True,
                    "persisted_name": roots[0].name,
                    "persisted_latency_seconds": roots[0].latency,
                    "observations": [o.model_dump(mode="json") for o in observations],
                    "scores": [s.model_dump(mode="json") for s in scores],
                }
                print(f"Verified {result['scenario']}: {len(observations)} observations, score={scores[0].value}")
            except Exception as exc:
                errors[trace_id] = f"{type(exc).__name__}: {exc}"
        if len(verified) == len(results):
            return [verified[r["trace_id"]] for r in results]
        time.sleep(2)
    raise RuntimeError(f"Ingestion verification timed out: {errors}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=120, help="Ingestion timeout in seconds")
    parser.add_argument("--verify-only", action="store_true", help="Verify the saved run without sending new traces")
    args = parser.parse_args()
    client = make_client()
    try:
        if not client.auth_check():
            raise RuntimeError("Langfuse authentication failed; check .env and local server")
        artifacts = HERE / "artifacts"
        artifacts.mkdir(exist_ok=True)
        path = artifacts / "latest-run.json"
        if args.verify_only:
            report = json.loads(path.read_text())
            results = report["traces"]
        else:
            run_id = f"demo-{uuid.uuid4().hex[:12]}"
            results = [run_case(client, run_id, s) for s in ("success", "slow-generation", "retrieval-error")]
            client.flush()
            # Save IDs before verification so a failed check can be investigated.
            report = {"run_id": run_id, "mode": "simulation", "created_at": datetime.now(timezone.utc).isoformat(), "traces": results}
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        report["traces"] = verify(client, results, args.timeout)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"\nReport: {path}")
        for result in results:
            print(f"{result['scenario']}: {result['trace_url']}")
    finally:
        client.shutdown()


if __name__ == "__main__":
    main()
