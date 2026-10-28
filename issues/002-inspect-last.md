# 002: `inspect --last` 打开最新轨迹

现在 `mini-agent inspect` 必须手动输入完整文件名，时间戳很难记。

## 要求

`mini-agent inspect --last`（无位置参数时）自动打开 `trajectories/` 下修改时间最新的 `.json` 文件。目录为空时给出友好提示，exit code 非 0。

## 验收标准

- 连续跑两个任务后，`inspect --last` 回放的是第二个任务的轨迹
- 空目录时行为符合上述要求
- 既有测试全部保持绿色

## Status

Done (c396a44): `inspect --last` picks newest *.json by mtime; empty/missing dir -> friendly message + exit 1. Covered by test_inspect_last_opens_newest / test_inspect_last_empty_dir.
