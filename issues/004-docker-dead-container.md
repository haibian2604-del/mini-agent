# 004: Docker 容器被外部停止后，execute() 的观察信息让模型困惑

当容器被外部 `docker stop`（或意外死亡）后，`DockerEnvironment.execute()` 返回的是 docker CLI 的原始报错文本，returncode 却可能是 0 或 127 之类。模型看到 "Cannot connect to the Docker daemon" 之类的观察会开始瞎猜（以为是自己的命令写错了），在错误方向上烧掉剩余步数。

## 要求

`execute()` 应识别"容器已不在运行"的情况，返回一条明确的观察信息（例如 sandbox 不可用、任务无法继续的说明），让模型/调用方能分辨"我的命令失败了"和"沙箱没了"。

## 验收标准

- 一个测试：构造容器不存在/已停止的场景（可 monkeypatch subprocess），断言返回信息明确区分两种失败
- 容器正常时的行为不变

## Status

Done: execute() detects "is not running"/"No such container"/daemon-down markers -> returncode -2 + explicit [sandbox unavailable] message telling the model not to retry. Healthy-container behavior unchanged. 4 tests incl. monkeypatched dead/daemon-down/normal.
