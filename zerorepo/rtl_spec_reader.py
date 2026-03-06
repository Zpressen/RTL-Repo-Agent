"""
RTL Spec Reader Module

从 rtl_dataset 目录读取 Markdown 格式的 RTL 项目规格说明，
并解析为标准化的项目数据结构。
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


# 默认路径配置
DEFAULT_RTL_DATASET_DIR = Path(__file__).parent.parent / "rtl_dataset"
# 输出目录放在当前工作目录下，避免权限问题
DEFAULT_RTL_OUTPUT_DIR = Path.cwd() / "rtl_outputs"


@dataclass
class RTLProjectSpec:
    """RTL 项目规格数据类"""
    project_name: str
    spec_file_path: Path
    spec_content: str
    output_dir: Path

    # 从 spec 中解析出来的关键信息
    top_module: Optional[str] = None
    language: Optional[str] = None
    toolchain: List[str] = field(default_factory=list)
    files: Dict[str, str] = field(default_factory=dict)  # filepath -> responsibility
    modules: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "repository_name": self.project_name,
            "repository_purpose": f"RTL project from spec: {self.spec_file_path.name}",
            "spec_file_path": str(self.spec_file_path),
            "output_dir": str(self.output_dir),
            "top_module": self.top_module,
            "language": self.language,
            "toolchain": self.toolchain,
            "files": self.files,
            "modules": self.modules,
        }


class RTLSpecReader:
    """RTL Spec 读取器"""

    def __init__(
        self,
        dataset_dir: Path = DEFAULT_RTL_DATASET_DIR,
        output_dir: Path = DEFAULT_RTL_OUTPUT_DIR
    ):
        """
        初始化 RTL Spec 读取器

        Args:
            dataset_dir: RTL spec 文件所在目录 (默认: rtl_dataset)
            output_dir: 生成代码的输出目录 (默认: rtl_outputs)
        """
        self.dataset_dir = Path(dataset_dir)
        self.output_dir = Path(output_dir)

        # 确保目录存在
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def list_spec_files(self) -> List[Path]:
        """
        列出 dataset_dir 中所有的 .md 文件

        Returns:
            Markdown 文件路径列表
        """
        spec_files = sorted(self.dataset_dir.glob("*.md"))
        return spec_files

    def get_project_name_from_filename(self, spec_file: Path) -> str:
        """
        从文件名提取项目名称

        Args:
            spec_file: spec 文件路径

        Returns:
            项目名称 (小写, 用下划线连接)
        """
        # 移除 .md 后缀
        name = spec_file.stem
        # 转换为小写, 空格和特殊字符替换为下划线
        name = re.sub(r'[-\s]+', '_', name)
        name = re.sub(r'[^a-z0-9_]', '', name.lower())
        return name

    def parse_spec_file(self, spec_file: Path) -> RTLProjectSpec:
        """
        解析单个 spec 文件

        Args:
            spec_file: Markdown 格式的 spec 文件路径

        Returns:
            RTLProjectSpec 对象
        """
        project_name = self.get_project_name_from_filename(spec_file)
        output_dir = self.output_dir / project_name

        # 读取文件内容
        with open(spec_file, 'r', encoding='utf-8') as f:
            spec_content = f.read()

        # 解析关键信息
        top_module = self._extract_top_module(spec_content)
        language = self._extract_language(spec_content)
        toolchain = self._extract_toolchain(spec_content)
        files = self._extract_file_structure(spec_content)
        modules = self._extract_modules(spec_content)

        return RTLProjectSpec(
            project_name=project_name,
            spec_file_path=spec_file,
            spec_content=spec_content,
            output_dir=output_dir,
            top_module=top_module,
            language=language,
            toolchain=toolchain,
            files=files,
            modules=modules,
        )

    def _extract_top_module(self, content: str) -> Optional[str]:
        """从 spec 中提取顶层模块名"""
        # 查找类似 "axi_uart_top" 或 module 后紧跟的名称
        patterns = [
            r'`(\w+)`\s+implements\s+(?:an?\s+)?\w+',  # `module_name` implements ...
            r'`(\w+)`\s+is\s+a',  # `module_name` is a ...
            r'module\s+(\w+)\s*\(',  # module module_name (
            r'^##\s+(\w+)\s*$',  # ## module_name (标题)
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_language(self, content: str) -> Optional[str]:
        """从 spec 中提取 RTL 语言版本"""
        # 查找 SystemVerilog 或 Verilog
        if "SystemVerilog" in content:
            match = re.search(r'SystemVerilog[- ](\d+)', content)
            if match:
                return f"SystemVerilog-{match.group(1)}"
            return "SystemVerilog"
        elif "Verilog" in content:
            return "Verilog"
        elif "VHDL" in content:
            return "VHDL"

        return None

    def _extract_toolchain(self, content: str) -> List[str]:
        """从 spec 中提取工具链信息"""
        toolchain = []

        if "iverilog" in content.lower():
            toolchain.append("iverilog")
        if "verilator" in content.lower():
            toolchain.append("verilator")
        if "svlint" in content.lower():
            toolchain.append("svlint")
        if "make" in content.lower() and "sim" in content.lower():
            toolchain.append("make")

        return toolchain

    def _extract_file_structure(self, content: str) -> Dict[str, str]:
        """从 spec 中提取文件结构"""
        files = {}

        # 查找 Repository Blueprint 部分
        blueprint_match = re.search(
            r'##\s+10\.\s+Repository Blueprint.*?(?=##|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )

        if blueprint_match:
            blueprint_content = blueprint_match.group(0)
            # 匹配文件路径和职责
            # 格式: path/to/file.ext  # 职责描述
            file_pattern = r'`?([\w./]+\.sv)`?\s*(?:#\s*)?([^\n]+)?'
            for match in re.finditer(file_pattern, blueprint_content):
                filepath = match.group(1).strip()
                responsibility = match.group(2).strip() if match.group(2) else ""
                files[filepath] = responsibility

        return files

    def _extract_modules(self, content: str) -> List[str]:
        """从 spec 中提取模块列表"""
        modules = []

        # 查找 Module Decomposition 部分
        decomp_match = re.search(
            r'##\s+9\.\s+Timing.*?Module Decomposition.*?(?=##|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )

        if decomp_match:
            decomp_content = decomp_match.group(0)
            # 匹配模块名
            for match in re.finditer(r'\|\s*`(\w+)`\s*\|', decomp_content):
                modules.append(match.group(1))

        return modules

    def read_all_specs(self) -> List[RTLProjectSpec]:
        """
        读取所有 spec 文件

        Returns:
            RTLProjectSpec 对象列表
        """
        spec_files = self.list_spec_files()
        specs = []

        for spec_file in spec_files:
            try:
                spec = self.parse_spec_file(spec_file)
                specs.append(spec)
            except Exception as e:
                print(f"Warning: Failed to parse {spec_file}: {e}")

        return specs

    def read_spec_by_name(self, project_name: str) -> Optional[RTLProjectSpec]:
        """
        根据项目名称读取对应的 spec 文件

        Args:
            project_name: 项目名称

        Returns:
            RTLProjectSpec 对象, 如果不存在则返回 None
        """
        # 尝试直接匹配文件名
        spec_file = self.dataset_dir / f"{project_name}.md"

        if not spec_file.exists():
            normalized_query = self.get_project_name_from_filename(Path(f"{project_name}.md"))
            # 尝试模糊匹配
            for md_file in self.dataset_dir.glob("*.md"):
                normalized_stem = self.get_project_name_from_filename(md_file)
                if (
                    project_name.lower() in md_file.stem.lower()
                    or normalized_query == normalized_stem
                ):
                    spec_file = md_file
                    break

        if not spec_file.exists():
            return None

        return self.parse_spec_file(spec_file)


def create_rtl_spec_reader() -> RTLSpecReader:
    """创建默认的 RTL Spec Reader"""
    return RTLSpecReader()


if __name__ == "__main__":
    # 测试代码
    reader = create_rtl_spec_reader()

    print("=== Available RTL Spec Files ===")
    spec_files = reader.list_spec_files()
    for f in spec_files:
        print(f"  - {f.name}")

    print("\n=== Parsed Projects ===")
    specs = reader.read_all_specs()
    for spec in specs:
        print(f"\nProject: {spec.project_name}")
        print(f"  Output Dir: {spec.output_dir}")
        print(f"  Top Module: {spec.top_module}")
        print(f"  Language: {spec.language}")
        print(f"  Toolchain: {spec.toolchain}")
        print(f"  Modules: {spec.modules}")
        print(f"  Files: {len(spec.files)} files")
