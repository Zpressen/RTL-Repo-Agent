#!/bin/bash
set -euo pipefail

# ============================================================================
# ZeroRepo Main Pipeline Runner (fixed-args version)
# Edit the variables below to match your setup.
# ============================================================================

# ---------- User-editable settings ----------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# RTL Mode: 设置为 true 来从 rtl_dataset 读取 spec
RTL_MODE=true
RTL_PROJECT=""  # 指定项目名称，留空则处理所有项目

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

    # 确定具体项目
    if [[ -n "${RTL_PROJECT}" ]]; then
        GENERATING_PROJECT="${RTL_OUTPUT}/${RTL_PROJECT}"
    else
        # 处理所有项目时使用临时目录
        GENERATING_PROJECT="${RTL_OUTPUT}/_temp"
    fi

    CHECKPOINT_DIR="${GENERATING_PROJECT}/zerorepo"
    REPO_DIR="${GENERATING_PROJECT}"
    PHASE="rtl_phase1"  # RTL 模式固定为 phase1
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
echo " Rebuild:    ${FORCE_REBUILD}"
echo " Resume:     ${RESUME}"
echo " Dry Run:    ${DRY_RUN}"
echo "=========================================="

mkdir -p "${CHECKPOINT_DIR}"
exec "${CMD[@]}"