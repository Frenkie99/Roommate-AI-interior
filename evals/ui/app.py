"""Roommate 评测平台 - Streamlit 入口"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st

from evals.dataset.loader import DatasetLoader
from evals.executor.result_store import ResultStore
from evals.ui.components.sidebar import render_sidebar
from evals.ui.components.data_table import render_data_table
from evals.ui.components.summary_charts import render_summary_charts
from evals.ui.components.image_comparison import render_image_comparison
from evals.ui.components.badcase_panel import render_badcase_panel

st.set_page_config(
    page_title="Roommate Eval Platform",
    page_icon="📊",
    layout="wide",
)

st.title("Roommate 评测平台")

# 初始化数据
loader = DatasetLoader()
store = ResultStore()

# 检查数据是否就绪
try:
    pairs = loader.load()
except FileNotFoundError:
    st.error("数据集未找到。请先运行: `python -m evals.dataset.generator`")
    st.stop()

try:
    store.load()
except FileNotFoundError:
    st.error("评测结果未找到。请先运行: `python -m evals.executor.runner`")
    st.stop()

# 侧边栏
filters = render_sidebar(loader)

# 主内容区
tab1, tab2, tab3, tab4 = st.tabs(["概览", "数据表", "图像对比", "Badcase 分析"])

with tab1:
    render_summary_charts(store)

with tab2:
    df = render_data_table(store, filters)

with tab3:
    render_image_comparison(store, loader)

with tab4:
    render_badcase_panel(store, loader)
