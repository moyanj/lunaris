# 重复执行100次
for i in {1..5}
do
    python -m lunaris.worker &
done
