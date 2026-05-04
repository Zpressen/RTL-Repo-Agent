#!/bin/bash
set -euo pipefail

# ============================================================================
# ZeroRepo Main Pipeline Runner (fixed-args version)
# Edit the variables below to match your setup.
# ============================================================================

# ---------- User-editable settings ----------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RTL_SPEC_INPUT="${1:-}"

# RTL Mode: 设置为 true 来从 rtl_dataset 读取 spec
RTL_MODE=true
RTL_PROJECT=""  # 指定项目名称，留空则处理所有项目；命令行第一个参数优先，可传项目名或 .md 路径
RTL_PIPELINE_MODE="${RTL_PIPELINE_MODE:-planner}" # planner | legacy

# SWE Mode (传统模式)
GENERATING_PROJECT="../eat_snake"

# Azure AD authentication (for Azure OpenAI token-based auth)
export AZURE_TENANT_ID="${AZURE_TENANT_ID:-72f988bf-86f1-41af-91ab-2d7cd011db47}"
export AZURE_TOKEN_SCOPE="${AZURE_TOKEN_SCOPE:-api://feb7b661-cac7-44a8-8dc1-163b63c23df2/.default}"

CONFIG="${PROJECT_ROOT}/configs/zerorepo_config.yaml"

# 根据模式设置路径
if [[ "${RTL_MODE}" == "true" ]]; then
    RTL_DATASET="${PROJECT_ROOT}/rtl_dataset"
    RTL_OUTPUT="${PROJECT_ROOT}/rtl_outputs"

    if [[ -z "${RTL_SPEC_INPUT}" && -n "${RTL_PROJECT}" ]]; then
        RTL_SPEC_INPUT="${RTL_PROJECT}"
    fi

    if [[ "${RTL_SPEC_INPUT}" == *.md || "${RTL_SPEC_INPUT}" == */* ]]; then
        if [[ ! -f "${RTL_SPEC_INPUT}" ]]; then
            echo "RTL spec file not found: ${RTL_SPEC_INPUT}" >&2
            exit 1
        fi
    fi

    # 确定具体项目
    if [[ -n "${RTL_SPEC_INPUT}" ]]; then
        if [[ "${RTL_SPEC_INPUT}" == *.md || "${RTL_SPEC_INPUT}" == */* ]]; then
            SPEC_BASENAME="$(basename "${RTL_SPEC_INPUT}")"
            PROJECT_STEM="${SPEC_BASENAME%.md}"
            GENERATING_PROJECT="${RTL_OUTPUT}/${PROJECT_STEM}"
        else
            GENERATING_PROJECT="${RTL_OUTPUT}/${RTL_SPEC_INPUT}"
        fi
    else
        # 处理所有项目时使用临时目录
        GENERATING_PROJECT="${RTL_OUTPUT}/_temp"
    fi

    CHECKPOINT_DIR="${GENERATING_PROJECT}/.zerorepo"
    REPO_DIR="${GENERATING_PROJECT}"
    if [[ "${RTL_PIPELINE_MODE}" == "planner" ]]; then
        PHASE="rtl_planner"
    else
        PHASE="rtl"
    fi
else
    CHECKPOINT_DIR="${GENERATING_PROJECT}/checkpoints"
    REPO_DIR="${GENERATING_PROJECT}/workspace"
    PHASE="all"          # all | design | implementation
fi

LOG_LEVEL="INFO"     # DEBUG | INFO | WARNING | ERROR
LOG_FILE="${CHECKPOINT_DIR}/zerorepo.log"

LLM_CONFIG=""        # e.g., "${PROJECT_ROOT}/configs/llm.yaml" (leave empty to disable)
FORCE_REBUILD=false  # true | false
RESUME=true         # true | false
DRY_RUN=false        # true | false

# ---------- Build command ----------
CMD=(
  python "${PROJECT_ROOT}/main.py"
  --config "${CONFIG}"
  --checkpoint "${CHECKPOINT_DIR}"
  --repo "${REPO_DIR}"
  --phase "${PHASE}"
  --log-level "${LOG_LEVEL}"
  --log-file "${LOG_FILE}"
)

if [[ -n "${LLM_CONFIG}" ]]; then
  CMD+=(--llm-config "${LLM_CONFIG}")
fi
if [[ "${FORCE_REBUILD}" == "true" ]]; then
  CMD+=(--force-rebuild)
fi
if [[ "${RESUME}" == "true" ]]; then
  CMD+=(--resume)
fi
if [[ "${DRY_RUN}" == "true" ]]; then
  CMD+=(--dry-run)
fi
if [[ -n "${RTL_SPEC_INPUT}" ]]; then
  CMD+=(--rtl-spec "${RTL_SPEC_INPUT}")
fi

# ---------- Run ----------
echo "=========================================="
echo " ZeroRepo Pipeline"
echo "=========================================="
echo " Config:     ${CONFIG}"
echo " Checkpoint: ${CHECKPOINT_DIR}"
echo " Repo:       ${REPO_DIR}"
echo " Phase:      ${PHASE}"
echo " Log Level:  ${LOG_LEVEL}"
echo " Log File:   ${LOG_FILE}"
echo " LLM Config: ${LLM_CONFIG:-<none>}"
echo " RTL Spec:   ${RTL_SPEC_INPUT:-<all .md files in rtl_dataset, sorted>}"
echo " RTL Mode:   ${RTL_PIPELINE_MODE:-planner}"
echo " Rebuild:    ${FORCE_REBUILD}"
echo " Resume:     ${RESUME}"
echo " Dry Run:    ${DRY_RUN}"
echo "=========================================="

mkdir -p "${CHECKPOINT_DIR}"
exec "${CMD[@]}"
