"""数据集加载器"""

from typing import List, Optional

from evals.config import METADATA_PATH
from evals.dataset.schemas import DatasetMetadata, ImagePair


class DatasetLoader:
    def __init__(self, metadata_path: Optional[str] = None):
        self.metadata_path = metadata_path or str(METADATA_PATH)
        self._metadata: Optional[DatasetMetadata] = None

    def load(self) -> List[ImagePair]:
        if self._metadata is None:
            self._metadata = DatasetMetadata.load(self.metadata_path)
        return self._metadata.pairs

    def filter(self, tags: Optional[List[str]] = None,
               style: Optional[str] = None,
               room_type: Optional[str] = None,
               split: Optional[str] = None) -> List[ImagePair]:
        pairs = self.load()
        if tags:
            pairs = [p for p in pairs if any(t in p.tags for t in tags)]
        if style:
            pairs = [p for p in pairs if p.style == style]
        if room_type:
            pairs = [p for p in pairs if p.room_type == room_type]
        if split:
            pairs = [p for p in pairs if p.dataset_split == split]
        return pairs

    def get_all_tags(self) -> List[str]:
        pairs = self.load()
        all_tags = set()
        for p in pairs:
            all_tags.update(p.tags)
        return sorted(all_tags)

    def get_all_styles(self) -> List[str]:
        pairs = self.load()
        return sorted(set(p.style for p in pairs))

    def get_all_room_types(self) -> List[str]:
        pairs = self.load()
        return sorted(set(p.room_type for p in pairs))

    def get_statistics(self) -> dict:
        pairs = self.load()
        splits = {}
        for p in pairs:
            splits[p.dataset_split] = splits.get(p.dataset_split, 0) + 1
        return {"total": len(pairs), "splits": splits}
