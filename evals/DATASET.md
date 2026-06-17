# 测试集数据与迁移自检（Dataset & Migration）

> 本文档说明评测**测试集的数据结构、路径解析规则**，并提供「换机器 / clone 后」的**数据完整性自检命令**。
> 目标：确保测试集在任何机器（Mac / Windows / Linux）上都能稳定运行、看得到图和评测结果。
> 方法学与北极星指标见 [METHODOLOGY.md](./METHODOLOGY.md)，本文只管「数据能不能跑起来」。

---

## 1. 测试集构成

| 文件 / 目录 | 作用 | 评测是否加载 |
|---|---|---|
| `evals/data/real_metadata.json` | **评测实际加载的测试集**，85 对（competitor 31 / standard 45 / corner_case 9） | ✅ 是 |
| `evals/data/candidates/` | 毛坯房原图（input） | ✅ 经 metadata 引用 |
| `output/` | AI 生成效果图（output） | ✅ 经 metadata 引用 |
| `evals/data/eval_results.json` | 评测结果（历史保留 + 新跑覆盖） | ✅ 读 / 写 |
| `evals/data/images/` | mock 配对图（10 对） | ⚠️ 仅 mock，非真实评测 |
| `evals/data/metadata.json` | mock 数据生成器产物 | ❌ 评测不读 |
| `evals/data/candidates_summary.csv` | 采集脚本中间产物 | ❌ 评测不加载 |

> **常见误解**：`metadata.json` 里是 Windows 绝对路径，看着像会出问题 —— 但评测代码（`evals/config.py`）加载的是 `real_metadata.json`，不碰它。

---

## 2. 路径解析规则（为什么跨平台能跑）

`real_metadata.json` 里每对的路径都是**相对路径**，由 `evals/scorer/clip_scorer.py` 的 `_resolve()` 动态解析：

```python
def _resolve(path: str) -> Path:
    p = Path(path)
    if p.is_absolute(): return p
    if path.startswith("data/"):  return EVALS_DIR / p      # → evals/data/...
    return PROJECT_ROOT / p                                   # → output/...
```

- `input_path`：形如 `data/candidates/xxx.jpg` → 相对 `evals/`
- `output_path`：形如 `output/xxx.png` → 相对项目根

而 `PROJECT_ROOT` / `EVALS_DIR` 由 `Path(__file__).resolve()` 在运行时算出，**零硬编码路径** → Mac / Windows / Linux 自动适配。

---

## 3. 数据完整性自检（clone 或迁移后必跑）

> 在**项目根目录**执行。两条都输出 0 = 测试集可稳定运行。

**① 引用完整性 —— 每对引用的图是否都在：**

```bash
python -c "import json;from pathlib import Path;m=json.load(open('evals/data/real_metadata.json',encoding='utf-8'))['pairs'];miss=[p['pair_id'] for p in m if not Path('evals/'+p['input_path']).exists() or not Path(p['output_path']).exists()];print('缺失对数:',len(miss),'| 总对数:',len(m));print(miss[:10])"
```

预期：`缺失对数: 0`

**② 文件健康性 —— 有没有 0 字节损坏：**

```bash
python -c "import json;from pathlib import Path;m=json.load(open('evals/data/real_metadata.json',encoding='utf-8'))['pairs'];bad=[p['pair_id'] for p in m if Path('evals/'+p['input_path']).stat().st_size==0 or Path(p['output_path']).stat().st_size==0];print('损坏对数:',len(bad),'| 总对数:',len(m))"
```

预期：`损坏对数: 0`

> 基线（commit `b6205af`）：85 对，引用 0 缺失、0 损坏。

---

## 4. 新机器迁移 Checklist（环境依赖，非数据）

下列项**不进 git**（敏感 / 体积大 / 可重建），需在新机器单独准备。配齐后测试集即可跑：

| 项 | 原因 | 准备方式 |
|---|---|---|
| `.env`（API Key） | 含密钥，gitignore | 填 Gemini / Segmind / DeepSeek 的 key |
| Python 环境 | 可重建 | `python -m venv venv && pip install -r requirements.txt` |
| `node_modules/` | gitignore | `npm install` |
| `sam3-model/` | 大文件，gitignore | 单独拷贝 / 下载模型 |
| CLIP 模型 | 首次运行联网下载 | 跑评测时自动拉 `openai/clip-vit-base-patch32` |

---

## 5. 如果自检报「缺失」

说明该图没进 git（可能被某条 `.gitignore` 规则误伤，如全局 `test_*.jpg`）。

```bash
# 查这张图被哪条规则挡住
git check-ignore -v <缺失的路径>

# 强制纳入（一旦 tracked，后续不会再被忽略）
git add -f <缺失的路径>
git commit -m "fix: 补传测试集缺失图" && git push
```
