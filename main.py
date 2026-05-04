#!/usr/bin/env python3
"""
ZeroRepo Main Entry Script

This script serves as the main entry point for the ZeroRepo system, responsible for:
1. Parsing command line arguments
2. Initializing system configuration
3. Creating and setting up global checkpoint manager
4. Starting the complete end-to-end code generation pipeline
"""

import argparse
import json
import sys
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any

from zerorepo.config.checkpoint_config import create_default_manager
from zerorepo.utils.logs import redirect_standard_streams, setup_logger


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="ZeroRepo: LLM-based Automated Code Generation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example Usage:
  # Basic usage with default configuration
  python main.py --config configs/zerorepo_config.yaml --checkpoint ./checkpoints --repo ./target_repo

  # Specify all parameters
  python main.py \\
    --config configs/zerorepo_config.yaml \\
    --checkpoint ./checkpoints \\
    --repo ./target_repo \\
    --log-level DEBUG \\
    --force-rebuild

  # Set API key via environment variable
  export OPENAI_API_KEY="your-api-key"
  python main.py --config configs/zerorepo_config.yaml --checkpoint ./checkpoints --repo ./target_repo

Supported LLM Models:
  - OpenAI: gpt-4, gpt-3.5-turbo
  - Anthropic: claude-3-sonnet, claude-3-haiku
  - Google: gemini-pro
  - Local models: ollama/*
        """
    )
    
    # Required arguments
    parser.add_argument(
        "--config", "-c",
        type=str,
        required=True,
        help="ZeroRepo configuration file path (YAML format)"
    )
    
    parser.add_argument(
        "--checkpoint", "-k", 
        type=str,
        required=True,
        help="Checkpoint directory path for saving intermediate states"
    )
    
    parser.add_argument(
        "--repo", "-r",
        type=str,
        required=True,
        help="Target repository path where generated code will be saved"
    )
    
    # Optional arguments
    parser.add_argument(
        "--log-level", "-l",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log level (default: INFO)"
    )
    
    parser.add_argument(
        "--log-file",
        type=str,
        help="Log file path, outputs to console if not specified"
    )
    
    parser.add_argument(
        "--force-rebuild", "-f",
        action="store_true",
        help="Force rebuild Docker containers and reset state"
    )
    
    parser.add_argument(
        "--resume", "-res",
        action="store_true", 
        help="Resume execution from checkpoint (skip completed phases)"
    )
    
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Dry run mode - only validate configuration without execution"
    )
    
    parser.add_argument(
        "--phase",
        type=str,
        choices=["all", "design", "implementation", "rtl", "rtl_phase1", "rtl_phase2", "rtl_planner"],
        default="all",
        help="Specify execution phase: 'all'=full pipeline, 'design'=design only, 'implementation'=implementation only, 'rtl'=RTL full pipeline with resume, 'rtl_phase1'=RTL SpecFacts parsing, 'rtl_phase2'=RTL Module Contract Realization (requires Phase 1 output), 'rtl_planner'=run the standalone RTL module planner"
    )

    parser.add_argument(
        "--rtl-spec",
        type=str,
        default=None,
        help="RTL spec file path or project name (used with rtl_phase1)"
    )

    parser.add_argument(
        "--llm-config",
        type=str,
        default=None,
        help="Path to LLM configuration file (YAML/JSON). "
             "Overrides the 'llm' section in the main config file."
    )
    
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="ZeroRepo 1.0.0"
    )
    
    return parser.parse_args()


def validate_args(args) -> bool:
    """Validate command line arguments"""
    errors = []
    
    # Check configuration file
    config_path = Path(args.config)
    if not config_path.exists():
        errors.append(f"Configuration file does not exist: {config_path}")
    elif not config_path.suffix.lower() in ['.yaml', '.yml']:
        errors.append(f"Configuration file must be YAML format: {config_path}")
    
    # Check checkpoint directory
    checkpoint_path = Path(args.checkpoint)
    try:
        checkpoint_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        errors.append(f"Cannot create checkpoint directory {checkpoint_path}: {e}")
    
    # Check target repository path
    repo_path = Path(args.repo)
    try:
        repo_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        errors.append(f"Cannot create target repository directory {repo_path}: {e}")
    
    # Output error messages
    if errors:
        print("❌ Argument validation failed:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True

def setup_logging(args) -> logging.Logger:
    """Initialize the logging system for ZeroRepo main entrypoint."""
    # 规范化 log level
    level_name = str(args.log_level).upper()
    level = getattr(logging, level_name, logging.INFO)

    redirect_standard_streams(args.log_file)

    # 拿一个带名字的 logger
    logger = logging.getLogger("zerorepo-main")

    logger = setup_logger(
        logger=logger,
        file_path=args.log_file,
        level=level,
    )

    sep = "=" * 60
    logger.info(sep)
    logger.info("🚀 ZeroRepo Automated Code Generation System Starting")
    logger.info(sep)
    logger.info("📋 Configuration file: %s", args.config)
    logger.info("💾 Checkpoint directory: %s", args.checkpoint)
    logger.info("📁 Target repository: %s", args.repo)
    logger.info("🔧 Execution phase: %s", args.phase)
    logger.info("📊 Log level: %s", level_name)

    if getattr(args, "force_rebuild", False):
        logger.info("🔄 Force rebuild mode enabled")
    if getattr(args, "resume", False):
        logger.info("⏯️ Resume mode enabled")
    if getattr(args, "dry_run", False):
        logger.info("🧪 Dry run mode enabled")

    return logger

def run_zerorepo(args, logger: logging.Logger) -> bool:
    """Run ZeroRepo main pipeline"""
    try:
        # Convert paths
        config_path = Path(args.config)
        checkpoint_dir = Path(args.checkpoint)
        repo_path = Path(args.repo)

        # RTL planner / phase pipeline
        if args.phase in ["rtl", "rtl_phase1", "rtl_phase2", "rtl_planner"]:
            logger.info("🔧 Initializing RTL Spec2Repo Phase 1...")

            # Load config to get LLM settings
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            llm_config_dict = config.get('llm', {})

            # Import RTL specific modules
            from zerorepo.rtl_spec_reader import RTLSpecReader, DEFAULT_RTL_DATASET_DIR

            # Determine spec source
            if args.rtl_spec:
                spec_path = Path(args.rtl_spec)
                if spec_path.exists() and spec_path.is_file():
                    # Direct file path
                    dataset_dir = spec_path.parent
                    project_name = spec_path.stem
                else:
                    # Project name
                    dataset_dir = DEFAULT_RTL_DATASET_DIR
                    project_name = args.rtl_spec
            else:
                dataset_dir = DEFAULT_RTL_DATASET_DIR
                project_name = None

            reader = RTLSpecReader(dataset_dir=dataset_dir)

            if project_name:
                # Process single project
                spec = reader.read_spec_by_name(project_name)
                if spec is None:
                    logger.error(f"Project not found: {project_name}")
                    return False
                specs = [spec]
            else:
                # Process all projects
                specs = reader.read_all_specs()
                if not specs:
                    logger.warning(f"No spec files found in {dataset_dir}")
                    return True

            logger.info(f"Found {len(specs)} project(s) to process")

            # Process each spec
            for spec in specs:
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing: {spec.project_name}")
                logger.info(f"{'='*60}")

                # Create checkpoint directory
                spec_output_dir = spec.output_dir
                spec_checkpoint_dir = spec_output_dir / ".zerorepo"
                spec_checkpoint_dir.mkdir(parents=True, exist_ok=True)

                if args.phase == "rtl_planner":
                    from zerorepo.rpg_gen.base.llm_client import LLMConfig
                    from zerorepo.rtl_impl.module_planner import PlannerRunner, PlannerTaskInput

                    planner_llm_config = None
                    if args.llm_config:
                        planner_llm_config = LLMConfig.from_source(args.llm_config)
                    elif llm_config_dict:
                        planner_llm_config = LLMConfig.from_dict(llm_config_dict)
                    else:
                        raise RuntimeError(
                            "rtl_planner requires LLM configuration, but neither --llm-config "
                            "nor config['llm'] is available."
                        )

                    planner_output_root = spec_checkpoint_dir / "module_planner" / "outputs"
                    planner_output_root.mkdir(parents=True, exist_ok=True)

                    def _discover_spec_images() -> list[str]:
                        import re
                        import urllib.parse

                        image_paths: list[str] = []
                        seen: set[str] = set()

                        for match in re.finditer(r'!\[[^\]]*\]\(([^)]+)\)', spec.spec_content):
                            raw_ref = match.group(1).strip()
                            if not raw_ref:
                                continue
                            decoded_ref = urllib.parse.unquote(raw_ref)
                            candidate = (spec.spec_file_path.parent / decoded_ref).resolve()
                            if candidate.exists() and candidate.is_file():
                                candidate_str = str(candidate)
                                if candidate_str not in seen:
                                    seen.add(candidate_str)
                                    image_paths.append(candidate_str)

                        figures_dir = spec.spec_file_path.parent / "figures"
                        if figures_dir.exists():
                            stem = spec.spec_file_path.stem.lower()
                            for image_path in sorted(figures_dir.iterdir()):
                                if not image_path.is_file():
                                    continue
                                suffix = image_path.suffix.lower()
                                if suffix not in {".png", ".jpg", ".jpeg", ".svg", ".webp", ".bmp"}:
                                    continue
                                if stem in image_path.stem.lower():
                                    image_str = str(image_path.resolve())
                                    if image_str not in seen:
                                        seen.add(image_str)
                                        image_paths.append(image_str)

                        return image_paths

                    task_input = PlannerTaskInput(
                        task_id=spec.project_name,
                        spec_md_files=[str(spec.spec_file_path.resolve())],
                        spec_images=_discover_spec_images(),
                        project_type="light_repo_spec2rtl",
                        notes="Standalone RTL module planning run from main.py",
                    )

                    planner_runner = PlannerRunner(
                        output_root=planner_output_root,
                        llm_config=planner_llm_config,
                        logger=logger,
                    )
                    merge_artifact = planner_runner.run(task_input, resume=args.resume, end_stage="stage6")
                    stage1_artifact_path = planner_output_root / "contracts.json"
                    modules_artifact_path = planner_output_root / "modules.json"
                    repo_skeleton_artifact_path = planner_output_root / "repo_skeleton.json"
                    module_skeletons_artifact_path = planner_output_root / "module_skeletons.json"
                    spec_blocks_artifact_path = planner_output_root / "spec_blocks.json"
                    module_plans_artifact_path = planner_output_root / "module_plans.json"
                    stage5_codegen_artifact_path = planner_output_root / "stage5_codegen.json"
                    stage6_merge_artifact_path = planner_output_root / "stage6_merge.json"
                    module_plan_json_dir = planner_output_root / "module_plan_json"
                    workspace_dir = planner_output_root.parent.parent / "workspace"
                    fragments_dir = workspace_dir / "fragments"
                    merged_dir = workspace_dir / "merged"

                    logger.info("✅ RTL module planner completed for %s", spec.project_name)
                    logger.info("  - planner outputs root: %s", planner_output_root)
                    logger.info("  - stage1 contracts artifact: %s", stage1_artifact_path)
                    logger.info("  - module-organized artifact: %s", modules_artifact_path)
                    logger.info("  - repo skeleton artifact: %s", repo_skeleton_artifact_path)
                    logger.info("  - module skeletons artifact: %s", module_skeletons_artifact_path)
                    logger.info("  - spec blocks artifact: %s", spec_blocks_artifact_path)
                    logger.info("  - module plans artifact: %s", module_plans_artifact_path)
                    logger.info("  - module plan json dir: %s", module_plan_json_dir)
                    logger.info("  - stage5 codegen artifact: %s", stage5_codegen_artifact_path)
                    logger.info("  - stage6 merge artifact: %s", stage6_merge_artifact_path)
                    logger.info("  - stage5 fragments dir: %s", fragments_dir)
                    logger.info("  - stage6 merged dir: %s", merged_dir)
                    logger.info("  - Stage6 merged modules: %s module(s)", len(merge_artifact.module_files))
                    continue

                # Check for resume - if Phase 1 outputs exist, skip Phase 1
                spec_facts_file = spec_checkpoint_dir / "spec_facts.json"
                rpg_file = spec_checkpoint_dir / "rpg.json"
                phase1_skipped = False

                if args.resume and spec_facts_file.exists() and rpg_file.exists():
                    can_resume_phase1 = False
                    try:
                        from zerorepo.rtl_impl.phase1_spec_parsing.spec_models import SpecFacts

                        with open(spec_facts_file, 'r', encoding='utf-8') as f:
                            resume_spec_facts_dict = json.load(f)
                        resume_spec_facts = SpecFacts.from_dict(resume_spec_facts_dict)
                        resume_spec_facts.check_phase1_completion()
                        can_resume_phase1 = bool(getattr(resume_spec_facts, "phase1_complete", False))
                    except Exception as e:
                        logger.warning(
                            "Resume validation for Phase 1 outputs failed, forcing Phase 1 rerun: %s",
                            e,
                        )

                    if can_resume_phase1:
                        logger.info(f"⏭️ Phase 1 skipped (resume mode, validated outputs exist): {spec.project_name}")
                        phase1_skipped = True
                    else:
                        logger.info(
                            "🔁 Resume mode found stale/incomplete Phase 1 outputs for %s; rerunning Phase 1",
                            spec.project_name,
                        )
                else:
                    # Save repo_data.json (compatible format)
                    repo_data = spec.to_dict()
                    repo_data_file = spec_checkpoint_dir / "repo_data.json"
                    with open(repo_data_file, 'w', encoding='utf-8') as f:
                        json.dump(repo_data, f, indent=2, ensure_ascii=False)

                    # Save full spec content
                    spec_content_file = spec_checkpoint_dir / "spec_content.md"
                    with open(spec_content_file, 'w', encoding='utf-8') as f:
                        f.write(spec.spec_content)

                    logger.info(f"SpecFacts saved to: {spec_checkpoint_dir}")
                    logger.info(f"  - repo_data.json")
                    logger.info(f"  - spec_content.md")

                # Run Phase 1: SpecFacts & Contract Grounding
                from zerorepo.rtl_impl.phase1_spec_parsing import SpecFactsDesigner

                # Default policy for RTL phase1:
                # - use agent by default
                # - strict agent mode by default (no regex fallback)
                # - optional override:
                #   RTL_PHASE1_USE_AGENT=false => disable agent
                #   RTL_PHASE1_ALLOW_REGEX_FALLBACK=true => non-strict mode
                llm_config = None
                use_agent_env = os.getenv("RTL_PHASE1_USE_AGENT", "").lower()
                use_agent = use_agent_env in {"1", "true", "yes", "on"} if use_agent_env else True
                allow_regex_fallback = os.getenv("RTL_PHASE1_ALLOW_REGEX_FALLBACK", "").lower() in {
                    "1", "true", "yes", "on"
                }
                strict_agent = not allow_regex_fallback

                if use_agent:
                    try:
                        from zerorepo.rpg_gen.base.llm_client import LLMConfig
                        if args.llm_config:
                            llm_config = LLMConfig.from_source(args.llm_config)
                        elif llm_config_dict:
                            llm_config = LLMConfig.from_dict(llm_config_dict)
                        else:
                            msg = (
                                "Agent mode requires LLM config, but neither --llm-config "
                                "nor config['llm'] is available."
                            )
                            if strict_agent:
                                raise RuntimeError(msg)
                            logger.warning("%s Falling back to regex parser for rtl_phase1.", msg)
                            use_agent = False
                        use_agent = use_agent and (llm_config is not None)
                    except Exception as e:
                        if strict_agent:
                            raise
                        logger.warning(
                            "LLM stack unavailable (%s). Falling back to regex parser for rtl_phase1.",
                            e
                        )
                        use_agent = False

                # Run SpecFactsDesigner (only if not skipped)
                if not phase1_skipped:
                    designer = SpecFactsDesigner(
                        llm_config=llm_config,
                        logger=logger,
                        use_agent=use_agent,
                        strict_agent=strict_agent,
                    )
                    spec_facts = designer.run(
                        spec_content=spec.spec_content,
                        spec_name=spec.project_name,
                        checkpoint_dir=spec_checkpoint_dir,
                    )

                    logger.info(f"  - spec_facts.json")
                    logger.info(f"  - phase1_diagnostics.json")

                    # Convert SpecFacts to RPG and save
                    from zerorepo.rtl_impl.phase1_spec_parsing import SpecFactsToRpgAdapter
                    adapter = SpecFactsToRpgAdapter(spec_facts)
                    rpg = adapter.create_rpg_from_specfacts()

                    rpg_file = spec_checkpoint_dir / "rpg.json"
                    with open(rpg_file, 'w', encoding='utf-8') as f:
                        json.dump(adapter.get_rpg_dict(rpg), f, indent=2, ensure_ascii=False)

                    logger.info(f"  - rpg.json")
                    logger.info(f"✅ Phase 1 completed for {spec.project_name}")
                else:
                    # Load existing spec_facts and rpg for Phase 2
                    with open(spec_facts_file, 'r', encoding='utf-8') as f:
                        spec_facts_dict = json.load(f)
                    # Note: rpg is needed for Phase 2, load it too
                    # For now, we'll reload it in Phase 2 section

                # ===== Phase 2: File-Centered Prop-Level Enrichment =====
                # Run Phase 2 if phase is 'rtl' or 'rtl_phase2'
                if args.phase in ["rtl", "rtl_phase2"]:
                    from zerorepo.rtl_impl.phase1_spec_parsing.spec_models import SpecFacts
                    from zerorepo.rtl_impl.phase2_module_graph.models import Phase2Contracts
                    from zerorepo.rtl_impl import RTLPropLevelAdapter

                    # Check for resume - if phase2_contracts.json exists, skip Phase 2
                    phase2_contracts_file = spec_checkpoint_dir / "phase2_contracts.json"
                    phase2_skipped = False

                    if args.resume and phase2_contracts_file.exists():
                        can_resume_phase2 = False
                        try:
                            with open(phase2_contracts_file, 'r', encoding='utf-8') as f:
                                phase2_contracts_dict = json.load(f)
                            phase2_contracts_resume = Phase2Contracts.from_dict(phase2_contracts_dict)
                            can_resume_phase2 = bool(
                                getattr(phase2_contracts_resume, "phase2_ready_for_impl_level", False)
                            )
                        except Exception as e:
                            logger.warning(
                                "Resume validation for Phase 2 outputs failed, forcing Phase 2 rerun: %s",
                                e,
                            )

                        if can_resume_phase2:
                            logger.info(
                                f"⏭️ Phase 2 skipped (resume mode, validated output exists): {spec.project_name}"
                            )
                            phase2_skipped = True
                        else:
                            logger.info(
                                "🔁 Resume mode found stale/incomplete Phase 2 outputs for %s; rerunning Phase 2",
                                spec.project_name,
                            )
                    else:
                        # Run Phase 2
                        logger.info(f"🔧 Running Phase 2: File-Centered Prop-Level Enrichment...")

                        # Import Phase 2 modules
                        from zerorepo.rtl_impl.phase2_module_graph import Phase2Designer

                        # Load spec_facts from file
                        with open(spec_facts_file, 'r', encoding='utf-8') as f:
                            spec_facts_dict = json.load(f)

                        # Reconstruct full SpecFacts object with enhanced fields
                        spec_facts = SpecFacts.from_dict(spec_facts_dict)

                        # Load rpg if Phase 1 was skipped
                        if phase1_skipped:
                            # Need to create a minimal RPG for Phase 2
                            from zerorepo.rpg_gen.base import RPG
                            rpg = RPG(
                                repo_name=spec_facts.project_name or "rtl_project",
                                repo_info=spec_facts.abstract or "",
                                excluded_files=[]
                            )
                            logger.info(f"  [Resuming] Loaded spec_facts, created minimal RPG for Phase 2")

                        # Run Phase 2
                        phase2_designer = Phase2Designer(
                            llm_config=llm_config,
                            checkpoint_dir=spec_checkpoint_dir,
                            use_agent=True,
                            strict_agent=True,
                        )

                        phase2_result = phase2_designer.run(
                            spec_facts=spec_facts,
                            rpg=rpg,
                        )

                        if phase2_result.get("success"):
                            logger.info(f"  - phase2_contracts.json")
                            logger.info(f"✅ Phase 2 completed for {spec.project_name}")
                        else:
                            logger.error(f"❌ Phase 2 failed for {spec.project_name}")
                            return False

                    if not phase2_contracts_file.exists():
                        logger.error("phase2_contracts.json not found for %s", spec.project_name)
                        return False

                    # Export repo_data.json for generic impl-level compatibility
                    with open(spec_facts_file, 'r', encoding='utf-8') as f:
                        spec_facts_dict = json.load(f)
                    spec_facts = SpecFacts.from_dict(spec_facts_dict)

                    with open(phase2_contracts_file, 'r', encoding='utf-8') as f:
                        phase2_contracts_dict = json.load(f)
                    phase2_contracts = Phase2Contracts.from_dict(phase2_contracts_dict)

                    adapter = RTLPropLevelAdapter(logger=logger)
                    adapter.export_repo_data(
                        spec_facts=spec_facts,
                        phase2_contracts=phase2_contracts,
                        checkpoint_dir=spec_checkpoint_dir,
                    )
                    logger.info("  - repo_data.json")

                    # Hand off to the generic implementation layer instead of
                    # stopping after repo_data export.
                    from zerorepo.config.checkpoint_config import create_default_manager
                    from zerorepo.zerorepo import ZeroRepo

                    create_default_manager(spec_checkpoint_dir)
                    repo_root = (spec_facts.repo_root or "").strip().strip("/")
                    target_repo_path = spec.output_dir / repo_root if repo_root else spec.output_dir / "workspace"
                    target_repo_path.mkdir(parents=True, exist_ok=True)

                    zero_repo = ZeroRepo(
                        config_path=config_path,
                        checkpoint_dir=spec_checkpoint_dir,
                        repo_path=target_repo_path,
                        logger=logger,
                    )

                    plan_batches, skeleton, rpg, graph_data = zero_repo.run_impl_level()
                    logger.info(
                        "✅ RTL compatible repo_data exported and impl_level completed for %s",
                        spec.project_name,
                    )

                    codegen_success = zero_repo.run_code_generation(
                        plan_batches=plan_batches,
                        skeleton=skeleton,
                        rpg=rpg,
                        graph_data=graph_data,
                    )
                    if not codegen_success:
                        logger.error(
                            "❌ RTL code generation failed for %s",
                            spec.project_name,
                        )
                        return False
                    logger.info(
                        "✅ RTL code generation completed for %s",
                        spec.project_name,
                    )

            # Summary
            if args.phase == "rtl":
                logger.info(f"\n{'='*60}")
                logger.info(f"🎉 RTL Pipeline completed for {len(specs)} project(s)")
                logger.info(f"  - Phase 1: spec_facts.json, rpg.json")
                logger.info(f"  - Phase 2: phase2_contracts.json")
                logger.info(f"  - Prop adapter: repo_data.json")
                logger.info(f"  - Impl level: skeleton.json, graph.json, tasks.json")
                logger.info(f"  - Code generation: TaskManager + Trae executor")
                logger.info(f"{'='*60}")
            elif args.phase == "rtl_phase1":
                logger.info(f"\n{'='*60}")
                logger.info(f"🎉 RTL Phase 1 completed for {len(specs)} project(s)")
                logger.info(f"{'='*60}")
            elif args.phase == "rtl_phase2":
                logger.info(f"\n{'='*60}")
                logger.info(f"🎉 RTL Phase 2 completed for {len(specs)} project(s)")
                logger.info(f"{'='*60}")
            elif args.phase == "rtl_planner":
                logger.info(f"\n{'='*60}")
                logger.info(f"🎉 RTL module planner completed for {len(specs)} project(s)")
                logger.info("  - outputs: .zerorepo/module_planner/outputs/contracts.json")
                logger.info("  - outputs: .zerorepo/module_planner/outputs/modules.json")
                logger.info("  - outputs: .zerorepo/module_planner/outputs/spec_blocks.json")
                logger.info("  - outputs: .zerorepo/module_planner/outputs/module_plans.json")
                logger.info(f"{'='*60}")

            return True

        logger.info("🔧 Initializing ZeroRepo system...")
        from zerorepo.zerorepo import ZeroRepo

        # Create global checkpoint manager
        logger.info(f"📋 Setting up global checkpoint manager: {checkpoint_dir}")
        create_default_manager(checkpoint_dir)

        # Dry run mode
        if args.dry_run:
            logger.info("🧪 Dry run mode - validating configuration only")
            zero_repo = ZeroRepo(config_path, checkpoint_dir, repo_path)
            logger.info("✅ Configuration validation passed, system initialized successfully")
            return True

        # Create ZeroRepo instance
        zero_repo = ZeroRepo(
            config_path=config_path,
            checkpoint_dir=checkpoint_dir,
            repo_path=repo_path,
            logger=logger  # Pass the logger with file configuration
        )

        # Override LLM config from --llm-config file if provided
        if args.llm_config:
            from zerorepo.rpg_gen.base.llm_client import LLMConfig
            llm_cfg = LLMConfig.from_source(args.llm_config)
            zero_repo.config["llm"] = llm_cfg.to_dict()
            logger.info(f"LLM config overridden from: {args.llm_config}")

        # Execute based on specified phase
        if args.phase == "design":
            logger.info("🎨 Executing design phase...")
            result = zero_repo.run_design_phase(resume=args.resume)
            logger.info("✅ Design phase completed")

        elif args.phase == "implementation":
            logger.info("⚡ Executing implementation phase...")
            result = zero_repo.run_implementation_phase(
                resume=args.resume,
                force_rebuild=args.force_rebuild
            )
            logger.info("✅ Implementation phase completed")

        else:  # phase == "all"
            logger.info("🔄 Executing full pipeline...")
            result = zero_repo.run()

        if result:
            logger.info("=" * 60)
            logger.info("🎉 ZeroRepo execution completed successfully!")
            logger.info(f"📁 Generated code saved in: {repo_path}")
            logger.info(f"💾 Intermediate files saved in: {checkpoint_dir}")
            logger.info("=" * 60)
        else:
            logger.error("=" * 60)
            logger.error("❌ ZeroRepo execution failed, check logs for details")
            logger.error("=" * 60)

        return bool(result)
        
    except KeyboardInterrupt:
        logger.warning("⚠️ User interrupted execution")
        return False
        
    except Exception as e:
        logger.error(f"❌ ZeroRepo execution failed: {e}")
        logger.debug("Detailed error information:", exc_info=True)
        return False


def main():
    """Main function"""
    # Parse command line arguments
    args = parse_args()
    
    # Validate arguments
    if not validate_args(args):
        sys.exit(1)
    
    # Setup logging
    logger = setup_logging(args)
    
    try:
        # Run ZeroRepo
        success = run_zerorepo(args, logger)
        
        if success:
            logger.info("🚀 ZeroRepo execution successful")
            sys.exit(0)
        else:
            logger.error("❌ ZeroRepo execution failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"💥 Main program exception: {e}")
        logger.debug("Detailed exception information:", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
