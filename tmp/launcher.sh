#!/bin/bash
# 用法: ssh jetson@... 'bash -s' < launcher.sh

# 把主任务脚本写到板上的 /tmp/whole_job.sh
cat > /tmp/whole_job.sh <<'EOF_JOB'
#!/bin/bash
set +e   # 不 set -e，让单个命令失败不影响整体任务
cd ~/Scout_mini_navigation

echo "=== $(date '+%Y-%m-%d %H:%M:%S') START ==="

echo "=== 备份 .git ==="
BACKUP_DIR="/home/jetson/Scout_mini_navigation_git_filterbackup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -a ./.git "$BACKUP_DIR/.git"
echo "备份到 $BACKUP_DIR"

echo "=== 写 filter index script ==="
cat > /tmp/filter_index.sh <<'EOF_FILTER'
#!/bin/bash
git rm -r --cached --ignore-unmatch install/ src/my_nav/maps/ src/my_nav/bags/ frontend/dist/ frontend/node_modules/ 2>/dev/null
git ls-files 2>/dev/null | grep -E '\.(pgm|pcd|pbstream|bag|gif|png|jpg|jpeg|mp4|mov|so(\.[0-9]+)?|bin|exe|pdf|zip|tar\.gz|tgz|7z|stl|dae|ply|mesh|wasm|map|jar|deb|rpm|dmg)$' | xargs -r git rm --cached --ignore-unmatch -- 2>/dev/null
exit 0
EOF_FILTER
chmod +x /tmp/filter_index.sh

echo "=== filter-branch 开始（预计 5-12 分钟）==="
FB_START=$(date +%s)
git filter-branch -f --index-filter /tmp/filter_index.sh --prune-empty --tag-name-filter cat -- --all 2>&1 | tail -30
FB_END=$(date +%s)
echo "filter-branch 耗时 $(( FB_END - FB_START )) 秒"

echo "=== 清理 original refs ==="
git for-each-ref --format='%(refname)' refs/original 2>/dev/null | xargs -n1 git update-ref -d 2>&1 | head -5

echo "=== reflog expire + gc ==="
git reflog expire --expire=now --all 2>&1 | tail -3
git gc --prune=now --aggressive 2>&1 | tail -5
echo "Final pack stats:"
git count-objects -v | grep -E "size-pack|count|in-pack"

echo "=== HEAD tree 大文件检查（应均为 0） ==="
for ext in pgm pcd pbstream bag gif png jpg so; do
  c=$(git ls-tree -r HEAD | grep -c "\.$ext$" || echo 0)
  echo "  .$ext: $c"
done

echo "=== HEAD tree 总文件数 ==="
git ls-tree -r HEAD | wc -l

echo "=== force-push 开始 ==="
PUSH_START=$(date +%s)
git push -f origin master --tags 2>&1 | tail -30
PUSH_END=$(date +%s)
echo "force-push 耗时 $(( PUSH_END - PUSH_START )) 秒"

echo "=== 核对 ==="
echo "local:  $(git rev-parse HEAD 2>&1)"
echo "remote: $(git rev-parse origin/master 2>&1)"

echo "=== GitHub repo size via API ==="
curl -s -H "Accept: application/vnd.github+json" https://api.github.com/repos/kunkunwei/Scout_mini_navigation | grep -oE '"(size|default_branch|full_name)":[^,]*' | head -5

echo "=== final pack 大小 ==="
git count-objects -v | grep -E "size-pack"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') DONE ==="
EOF_JOB

chmod +x /tmp/whole_job.sh
echo "Main script written to /tmp/whole_job.sh"

# 后台启动，detach
nohup /tmp/whole_job.sh > /tmp/whole_job.log 2>&1 &
PID=$!
echo "Main job started, PID=$PID"
disown
exit 0
