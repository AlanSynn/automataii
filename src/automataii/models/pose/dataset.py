"""Dataset configuration for pose detection."""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .base import BaseConfig


@dataclass
class PaperInfo(BaseConfig):
    """Information about the dataset paper."""
    author: str
    title: str
    container: str
    year: str
    homepage: str


@dataclass
class KeypointInfo(BaseConfig):
    """Keypoint definition."""
    name: str
    id: int
    color: List[int]
    type: str
    swap: str = ""


@dataclass
class SkeletonInfo(BaseConfig):
    """Skeleton link definition."""
    link: Tuple[str, str]
    id: int
    color: List[int]


@dataclass
class CocoDatasetInfo(BaseConfig):
    """COCO dataset information and structure."""
    dataset_name: str = "coco"
    paper_info: PaperInfo = field(default_factory=lambda: PaperInfo(
        author="Lin, Tsung-Yi and Maire, Michael and Belongie, Serge and Hays, James and Perona, Pietro and Ramanan, Deva and Dollár, Piotr and Zitnick, C Lawrence",
        title="Microsoft coco: Common objects in context",
        container="European conference on computer vision",
        year="2014",
        homepage="http://cocodataset.org/"
    ))
    keypoint_info: Dict[int, KeypointInfo] = field(default_factory=dict)
    skeleton_info: Dict[int, SkeletonInfo] = field(default_factory=dict)
    joint_weights: List[float] = field(default_factory=list)
    sigmas: List[float] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize COCO keypoints and skeleton if not provided."""
        if not self.keypoint_info:
            self.keypoint_info = self._get_coco_keypoints()
        if not self.skeleton_info:
            self.skeleton_info = self._get_coco_skeleton()
        if not self.joint_weights:
            self.joint_weights = [
                1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.2, 1.2, 1.5, 1.5,
                1.0, 1.0, 1.2, 1.2, 1.5, 1.5
            ]
        if not self.sigmas:
            self.sigmas = [
                0.026, 0.025, 0.025, 0.035, 0.035, 0.079, 0.079, 0.072, 0.072,
                0.062, 0.062, 0.107, 0.107, 0.087, 0.087, 0.089, 0.089
            ]
    
    @staticmethod
    def _get_coco_keypoints() -> Dict[int, Dict]:
        """Get COCO keypoint definitions."""
        return {
            0: dict(name="nose", id=0, color=[51, 153, 255], type="upper", swap=""),
            1: dict(name="left_eye", id=1, color=[51, 153, 255], type="upper", swap="right_eye"),
            2: dict(name="right_eye", id=2, color=[51, 153, 255], type="upper", swap="left_eye"),
            3: dict(name="left_ear", id=3, color=[51, 153, 255], type="upper", swap="right_ear"),
            4: dict(name="right_ear", id=4, color=[51, 153, 255], type="upper", swap="left_ear"),
            5: dict(name="left_shoulder", id=5, color=[0, 255, 0], type="upper", swap="right_shoulder"),
            6: dict(name="right_shoulder", id=6, color=[255, 128, 0], type="upper", swap="left_shoulder"),
            7: dict(name="left_elbow", id=7, color=[0, 255, 0], type="upper", swap="right_elbow"),
            8: dict(name="right_elbow", id=8, color=[255, 128, 0], type="upper", swap="left_elbow"),
            9: dict(name="left_wrist", id=9, color=[0, 255, 0], type="upper", swap="right_wrist"),
            10: dict(name="right_wrist", id=10, color=[255, 128, 0], type="upper", swap="left_wrist"),
            11: dict(name="left_hip", id=11, color=[0, 255, 0], type="lower", swap="right_hip"),
            12: dict(name="right_hip", id=12, color=[255, 128, 0], type="lower", swap="left_hip"),
            13: dict(name="left_knee", id=13, color=[0, 255, 0], type="lower", swap="right_knee"),
            14: dict(name="right_knee", id=14, color=[255, 128, 0], type="lower", swap="left_knee"),
            15: dict(name="left_ankle", id=15, color=[0, 255, 0], type="lower", swap="right_ankle"),
            16: dict(name="right_ankle", id=16, color=[255, 128, 0], type="lower", swap="left_ankle"),
        }
    
    @staticmethod
    def _get_coco_skeleton() -> Dict[int, Dict]:
        """Get COCO skeleton link definitions."""
        return {
            0: dict(link=("left_ankle", "left_knee"), id=0, color=[0, 255, 0]),
            1: dict(link=("left_knee", "left_hip"), id=1, color=[0, 255, 0]),
            2: dict(link=("right_ankle", "right_knee"), id=2, color=[255, 128, 0]),
            3: dict(link=("right_knee", "right_hip"), id=3, color=[255, 128, 0]),
            4: dict(link=("left_hip", "right_hip"), id=4, color=[51, 153, 255]),
            5: dict(link=("left_shoulder", "left_hip"), id=5, color=[51, 153, 255]),
            6: dict(link=("right_shoulder", "right_hip"), id=6, color=[51, 153, 255]),
            7: dict(link=("left_shoulder", "right_shoulder"), id=7, color=[51, 153, 255]),
            8: dict(link=("left_shoulder", "left_elbow"), id=8, color=[0, 255, 0]),
            9: dict(link=("right_shoulder", "right_elbow"), id=9, color=[255, 128, 0]),
            10: dict(link=("left_elbow", "left_wrist"), id=10, color=[0, 255, 0]),
            11: dict(link=("right_elbow", "right_wrist"), id=11, color=[255, 128, 0]),
            12: dict(link=("left_eye", "right_eye"), id=12, color=[51, 153, 255]),
            13: dict(link=("nose", "left_eye"), id=13, color=[51, 153, 255]),
            14: dict(link=("nose", "right_eye"), id=14, color=[51, 153, 255]),
            15: dict(link=("left_eye", "left_ear"), id=15, color=[51, 153, 255]),
            16: dict(link=("right_eye", "right_ear"), id=16, color=[51, 153, 255]),
            17: dict(link=("left_ear", "left_shoulder"), id=17, color=[51, 153, 255]),
            18: dict(link=("right_ear", "right_shoulder"), id=18, color=[51, 153, 255]),
        }


@dataclass
class DataConfig(BaseConfig):
    """Data configuration for pose detection."""
    image_size: List[int] = field(default_factory=lambda: [192, 256])
    heatmap_size: List[int] = field(default_factory=lambda: [48, 64])
    num_output_channels: int = 17
    num_joints: int = 17
    dataset_channel: List[List[int]] = field(default_factory=lambda: [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]])
    inference_channel: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16])
    soft_nms: bool = False
    nms_thr: float = 1.0
    oks_thr: float = 0.9
    vis_thr: float = 0.2
    use_gt_bbox: bool = True
    det_bbox_thr: float = 0.0
    bbox_file: str = ""


@dataclass
class ChannelConfig(BaseConfig):
    """Channel configuration for model input/output."""
    num_output_channels: int = 17
    dataset_joints: int = 17
    dataset_channel: List[List[int]] = field(default_factory=lambda: [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]])
    inference_channel: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16])