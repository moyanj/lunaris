from lunaris.master.file_store import FileStateStore

# 兼容现有导入路径，默认仍然使用文件后端。
PersistentStateStore = FileStateStore

