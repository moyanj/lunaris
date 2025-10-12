#!/bin/bash

# 检查当前目录是否有必要的结构
if [ ! -d "proto" ] || [ ! -f "proto/common.proto" ]; then
  echo "❌ 错误：请在项目根目录下运行此脚本"
  echo "当前目录结构缺失 'proto/' 或 'proto/common.proto'"
  exit 1
fi

# 检查 protoc 是否安装
if ! command -v protoc &> /dev/null; then
  echo "❌ 错误：protoc 未安装，请先安装 protobuf 编译器"
  echo "Ubuntu/Debian: sudo apt install -y protobuf-compiler"
  echo "macOS: brew install protobuf"
  exit 1
fi

# 输出路径
OUTPUT_DIR="./lunaris/proto"

# 创建输出目录（如果不存在）
mkdir -p "${OUTPUT_DIR}"

# 编译 proto 文件
PROTOC_CMD="protoc -I=proto"

# 支持的 proto 文件列表（可扩展）
PROTO_FILES=(
  "proto/common.proto"
  "proto/worker.proto"
  "proto/client.proto"
)

echo "🔍 正在编译 proto 文件到 ${OUTPUT_DIR} ..."

# 构建 protoc 命令并执行
${PROTOC_CMD} \
  --python_out="${OUTPUT_DIR}" \
  --pyi_out="${OUTPUT_DIR}" \
  "${PROTO_FILES[@]}"

find "${OUTPUT_DIR}" -type f -name "*.py" -o -name "*.pyi" | while read -r file; do
  sed -i.bak 's/import common_pb2/from lunaris.proto import common_pb2/g' "$file"
  rm -f "$file.bak"
done

echo "✅ Protobuf 编译完成！生成的文件在 ${OUTPUT_DIR}"
