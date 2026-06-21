"""结构评分器消融实验 — 用数据找出「哪种结构度量最贴合人工判断」

背景（见 PROGRESS.md / ROADMAP.md 阶段 2）：
现有 structural_fidelity = 0.6*Canny边缘SSIM + 0.4*灰度SSIM，vs 人工「结构保真」仅 +0.17（未达显著）。
猜想：灰度SSIM 测的是「整体外观相似度」，而好装修本就大改外观 → 这一项可能在拖后腿；
真正该测的是「建筑结构（墙/门窗/透视线/户型）是否保留」，应聚焦粗尺度布局与主导直线，避开家具细节边缘。

本脚本对每个候选度量，计算其在 85 对图上的值，再与人工 structural 金标准算 Spearman，
排序输出 → 选出显著正相关的度量重写评分器。纯实验脚本，不改生产代码。

运行：evals/.venv/bin/python -m evals.scorer.structural_ablation
"""

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evals.config import EVALS_DIR, PROJECT_ROOT
from evals.dataset.loader import DatasetLoader
from evals.scorer.gold_store import GoldStore
from evals.scorer.credibility import spearman, pearson


def _resolve(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    if str(path).startswith("data/"):
        return EVALS_DIR / p
    return PROJECT_ROOT / p


def _gray(path: str, size=(256, 256)) -> np.ndarray:
    img = Image.open(_resolve(path)).convert("RGB").resize(size)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)


# ----------------------------- 候选度量（越高=结构越保留）-----------------------------

def m_ssim_gray(gi, go):
    """灰度 SSIM（现有 40% 分量）—— 疑似拖后腿项。"""
    return ssim(gi, go, data_range=255)


def m_ssim_canny(gi, go):
    """Canny 边缘 SSIM（现有 60% 分量）。"""
    return ssim(cv2.Canny(gi, 100, 200), cv2.Canny(go, 100, 200), data_range=255)


def m_current(gi, go):
    """现有组合：0.6*边缘 + 0.4*灰度。"""
    return 0.6 * m_ssim_canny(gi, go) + 0.4 * m_ssim_gray(gi, go)


def m_ssim_lowres(gi, go):
    """超低分辨率灰度 SSIM（64x64）—— 只比「粗布局/明暗块」，抹掉家具细节。"""
    a = cv2.resize(gi, (64, 64)); b = cv2.resize(go, (64, 64))
    return ssim(a, b, data_range=255)


def m_ssim_blur(gi, go):
    """重高斯模糊后灰度 SSIM —— 抹掉纹理/家具，保留大结构明暗。"""
    a = cv2.GaussianBlur(gi, (0, 0), 6); b = cv2.GaussianBlur(go, (0, 0), 6)
    return ssim(a, b, data_range=255)


def _orient_hist(g, bins=18):
    """梯度方向直方图（捕捉主导直线/透视结构的朝向分布）。"""
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    ang = (np.arctan2(gy, gx) % np.pi)  # 0..pi（无向）
    hist, _ = np.histogram(ang, bins=bins, range=(0, np.pi), weights=mag)
    s = hist.sum()
    return hist / s if s else hist


def m_orient_corr(gi, go):
    """梯度方向直方图相关 —— 透视/墙线朝向是否一致，对家具增加更鲁棒。"""
    hi, ho = _orient_hist(gi), _orient_hist(go)
    r = pearson(list(hi), list(ho))
    return r if r is not None else 0.0


def m_long_line_overlap(gi, go):
    """长直线掩膜重叠（Hough）—— 墙/天花/地面交界等建筑长线是否保留。"""
    def line_mask(g):
        edges = cv2.Canny(g, 80, 200)
        mask = np.zeros_like(g, dtype=np.uint8)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                                minLineLength=80, maxLineGap=10)
        if lines is not None:
            for x1, y1, x2, y2 in lines[:, 0]:
                cv2.line(mask, (x1, y1), (x2, y2), 255, 3)
        return mask > 0
    a, b = line_mask(gi), line_mask(go)
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return inter / union if union else 0.0


CANDIDATES = {
    "ssim_gray (现40%)": m_ssim_gray,
    "ssim_canny (现60%)": m_ssim_canny,
    "current 组合": m_current,
    "ssim_lowres64": m_ssim_lowres,
    "ssim_blur6": m_ssim_blur,
    "orient_hist_corr": m_orient_corr,
    "long_line_overlap": m_long_line_overlap,
}


def main():
    pairs = {p.pair_id: p for p in DatasetLoader().load()}
    gold = GoldStore().load()
    ids = sorted(set(pairs) & set(gold))
    human = {pid: gold[pid]["scores"].get("structural") for pid in ids}
    ids = [pid for pid in ids if human[pid] is not None]
    print(f"可用样本: {len(ids)} 对（与人工 structural 金标准重叠）\n")

    # 预载灰度图，避免每个度量重复读盘
    grays = {}
    for pid in ids:
        p = pairs[pid]
        grays[pid] = (_gray(p.input_path), _gray(p.output_path))

    n = len(ids)
    thr = round(1.96 / (n - 1) ** 0.5, 3)
    print(f"显著阈值 |Spearman| ≈ {thr} (n={n}, p<0.05)\n")
    print(f"{'候选结构度量':<22}{'Spearman':>10}{'Pearson':>10}   判读")
    print("-" * 58)

    rows = []
    for name, fn in CANDIDATES.items():
        vals = [fn(*grays[pid]) for pid in ids]
        hs = [human[pid] for pid in ids]
        sp = spearman(vals, hs)
        pe = pearson(vals, hs)
        rows.append((name, sp, pe))

    for name, sp, pe in sorted(rows, key=lambda r: -(r[1] or -9)):
        sig = "✅显著正相关" if (sp is not None and sp > thr) else \
              ("⚠️弱正" if (sp is not None and sp > 0) else "🔴零/负相关")
        print(f"{name:<22}{(sp if sp is not None else 0):>+10.3f}"
              f"{(pe if pe is not None else 0):>+10.3f}   {sig}")

    print("\n结论：选 Spearman 最高且过显著阈值的度量，重写 RealStructuralFidelityScorer。")


if __name__ == "__main__":
    main()
