# 003: 交互模式下连续任务的轨迹会互相覆盖

`run.py` 用秒级时间戳给轨迹命名（`%Y%m%d-%H%M%S`）。交互模式下连续跑两个快任务（比如各只有 1-2 步）落在同一秒内时，第二个任务会**覆盖**第一个任务的轨迹文件——数据丢失。

## 复现

交互模式连续提交两个简单任务（如 "运行 echo hi"），在 1 秒内先后落盘，第一条轨迹消失。

## 要求

保证任何情况下轨迹文件名不冲突，且文件名仍可读、按时间排序不变。

## 验收标准

- 一个测试：monkeypatch `datetime`（或注入时钟）模拟同秒两次落盘，断言两个文件都存在且内容分别是各自任务的
- 全部既有测试保持绿色

## Status

Done: _trajectory_path() uses microsecond timestamps plus -N suffix when the file exists (frozen-clock safe). Regression test test_trajectory_names_never_collide.
