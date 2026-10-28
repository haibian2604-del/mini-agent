# 005: parse_action 对不写语言标注的代码块过于严格

部分模型（以及某些采样温度下）会输出不带 `bash` 标注的代码块：

    THOUGHT: ...
    ```
    echo hello
    ```

当前 `parse_action` 只认 ` ```bash `，这类回复全部报 FormatError，触发无意义的重试（烧钱且慢）。

## 要求

这是一个**产品决策 + 实现**的任务：

1. 决定策略：只放宽到"无标注代码块"，其他语言标注（```python 等）是否允许？说出你的理由
2. 实现，注意与"恰好一个代码块"约束的组合语义
3. 考虑回归风险：放宽后，模型在 THOUGHT 里解释性贴代码片段会不会造成误抓？

## 验收标准

- 新增测试覆盖：无标注块被接受、```python 块按你选的策略处理、混合场景不误抓
- 全部既有测试保持绿色

## Status

Done: strategy = accept bash-labeled + unlabeled; other language labels ignored (not counted, cannot run in bash). Exactly-one constraint applies to candidates. 5 new tests incl. mixed python-snippet-no-false-positive.
