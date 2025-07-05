# 重复执行100次
for i in {1..100}
do
    python -m lunaris.worker &
done
