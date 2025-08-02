#!/usr/bin/env python3
"""
메커니즘 시스템 종합 검증 스크립트
모든 메커니즘 타입의 생성, 시각화, 애니메이션 기능을 자동으로 검증합니다.
"""

import sys
import time
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import numpy as np

from automataii.ui.main_window import AutomataDesigner
from automataii.ui.tabs.mechanism_design.tab import MechanismDesignTab

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MechanismVerificationTester:
    """메커니즘 시스템 종합 검증 클래스"""
    
    # 검증할 메커니즘 타입과 테스트 케이스
    MECHANISM_TEST_CASES = {
        "4-Bar Linkage": {
            "type": "4-Bar Linkage",
            "parameters": {
                "a": 100.0,  # Input link length
                "b": 150.0,  # Coupler link length  
                "c": 120.0,  # Output link length
                "d": 200.0,  # Ground link length
                "p_x": 50.0, # Coupler point x
                "p_y": 30.0  # Coupler point y
            },
            "key_points": {
                "ground_pivot_1": [0, 0],
                "ground_pivot_2": [200, 0],
                "crank_end": [100, 0],
                "rocker_end": [150, 0]
            },
            "expected_visuals": 4  # driver, coupler, rocker, marker
        },
        "Cam & Follower": {
            "type": "Cam & Follower", 
            "parameters": {
                "cam_radius": 60.0,
                "follower_offset": 0.0,
                "lift_height": 40.0,
                "cam_rotation_speed": 1.0
            },
            "key_points": {
                "cam_center": [0, 0],
                "follower_start": [100, 0]
            },
            "expected_visuals": 2  # cam, follower
        },
        "Gears (Simple Pair)": {
            "type": "Gears (Simple Pair)",
            "parameters": {
                "gear1_radius": 50.0,
                "gear2_radius": 75.0,
                "center_distance": 125.0,
                "gear1_teeth": 20,
                "gear2_teeth": 30
            },
            "key_points": {
                "gear1_center": [0, 0],
                "gear2_center": [125, 0]
            },
            "expected_visuals": 4  # gear1, gear2, spoke1, spoke2
        },
        "Belt": {
            "type": "Belt",
            "parameters": {
                "pulley1_radius": 40.0,
                "pulley2_radius": 60.0,
                "center_distance": 150.0,
                "belt_speed": 1.0
            },
            "key_points": {
                "pulley1_center": [0, 0],
                "pulley2_center": [150, 0]
            },
            "expected_visuals": 4  # pulley1, pulley2, belt, marker
        },
        "Spring": {
            "type": "Spring",
            "parameters": {
                "spring_length": 100.0,
                "spring_constant": 1000.0,
                "mass": 5.0,
                "damping": 10.0
            },
            "key_points": {
                "anchor1": [0, 0],
                "anchor2": [100, 0],
                "mass_position": [50, 0]
            },
            "expected_visuals": 4  # anchor1, spring, mass, anchor2
        }
    }
    
    def __init__(self):
        self.app = None
        self.main_window = None
        self.mechanism_tab = None
        self.test_results = {}
        
    def setup_application(self):
        """PyQt 애플리케이션 초기화"""
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()
            
        # 메인 윈도우 생성
        self.main_window = AutomataDesigner()
        
        # 메커니즘 디자인 탭 찾기
        for i in range(self.main_window.tab_widget.count()):
            tab = self.main_window.tab_widget.widget(i)
            if isinstance(tab, MechanismDesignTab):
                self.mechanism_tab = tab
                break
                
        if not self.mechanism_tab:
            raise RuntimeError("메커니즘 디자인 탭을 찾을 수 없습니다.")
            
        logger.info("애플리케이션 초기화 완료")
        
    def create_test_mechanism_data(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """테스트용 메커니즘 데이터 생성"""
        
        # 기본 layer_data 구조
        layer_data = {
            "type": test_case["type"],
            "original_json_type": test_case["type"],
            "parameters": test_case["parameters"],
            "key_points": test_case["key_points"],
            "full_simulation_data": self.generate_mock_simulation_data(test_case),
            "transform_params": {
                "rotation": 0.0,
                "scale": 1.0,
                "offset_x": 0.0,
                "offset_y": 0.0
            }
        }
        
        return layer_data
        
    def generate_mock_simulation_data(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """테스트용 시뮬레이션 데이터 생성"""
        
        mech_type = test_case["type"]
        params = test_case["parameters"]
        key_points = test_case["key_points"]
        
        # 30 프레임의 애니메이션 데이터 생성
        num_frames = 30
        
        if mech_type == "4-Bar Linkage":
            return self.generate_linkage_simulation(params, key_points, num_frames)
        elif mech_type == "Cam & Follower":
            return self.generate_cam_simulation(params, key_points, num_frames)
        elif mech_type == "Gears (Simple Pair)":
            return self.generate_gear_simulation(params, key_points, num_frames)
        elif mech_type == "Belt":
            return self.generate_belt_simulation(params, key_points, num_frames)
        elif mech_type == "Spring":
            return self.generate_spring_simulation(params, key_points, num_frames)
        else:
            return {}
            
    def generate_linkage_simulation(self, params: Dict, key_points: Dict, num_frames: int) -> Dict:
        """4절 링키지 시뮬레이션 데이터 생성"""
        
        a, b, c, d = params["a"], params["b"], params["c"], params["d"]
        
        # Ground pivots
        p1 = np.array(key_points["ground_pivot_1"])
        p2 = np.array(key_points["ground_pivot_2"])
        
        joint_positions = {
            "p1_positions": [],
            "p2_positions": [],
            "p3_positions": [],
            "p4_positions": []
        }
        
        coupler_path = []
        
        for i in range(num_frames):
            theta = 2 * np.pi * i / num_frames
            
            # Calculate P3 (end of input link)
            p3 = p1 + a * np.array([np.cos(theta), np.sin(theta)])
            
            # Calculate P4 using coupler constraint
            # This is a simplified calculation
            p4 = p2 + c * np.array([np.cos(theta + np.pi/3), np.sin(theta + np.pi/3)])
            
            joint_positions["p1_positions"].append(p1.tolist())
            joint_positions["p2_positions"].append(p2.tolist())
            joint_positions["p3_positions"].append(p3.tolist())
            joint_positions["p4_positions"].append(p4.tolist())
            
            # Coupler point calculation
            coupler_center = (p3 + p4) / 2
            coupler_path.append(coupler_center.tolist())
            
        return {
            "joint_positions": joint_positions,
            "coupler_path": coupler_path
        }
        
    def generate_cam_simulation(self, params: Dict, key_points: Dict, num_frames: int) -> Dict:
        """캠 메커니즘 시뮬레이션 데이터 생성"""
        
        cam_center = np.array(key_points["cam_center"])
        follower_start = np.array(key_points["follower_start"])
        
        cam_positions = []
        follower_positions = []
        
        for i in range(num_frames):
            theta = 2 * np.pi * i / num_frames
            
            # Cam rotation
            cam_positions.append(cam_center.tolist())
            
            # Follower motion (simple harmonic)
            lift = params["lift_height"] * np.sin(theta)
            follower_pos = follower_start + np.array([0, lift])
            follower_positions.append(follower_pos.tolist())
            
        return {
            "cam_positions": cam_positions,
            "follower_positions": follower_positions
        }
        
    def generate_gear_simulation(self, params: Dict, key_points: Dict, num_frames: int) -> Dict:
        """기어 시뮬레이션 데이터 생성"""
        
        gear1_center = np.array(key_points["gear1_center"])
        gear2_center = np.array(key_points["gear2_center"])
        
        gear1_angles = []
        gear2_angles = []
        
        gear_ratio = params["gear1_radius"] / params["gear2_radius"]
        
        for i in range(num_frames):
            theta1 = 2 * np.pi * i / num_frames
            theta2 = -theta1 * gear_ratio  # Opposite direction
            
            gear1_angles.append(theta1)
            gear2_angles.append(theta2)
            
        return {
            "gear1_center": gear1_center.tolist(),
            "gear2_center": gear2_center.tolist(),
            "gear1_angles": gear1_angles,
            "gear2_angles": gear2_angles
        }
        
    def generate_belt_simulation(self, params: Dict, key_points: Dict, num_frames: int) -> Dict:
        """벨트 시뮬레이션 데이터 생성"""
        
        pulley1_center = np.array(key_points["pulley1_center"])
        pulley2_center = np.array(key_points["pulley2_center"])
        
        belt_positions = []
        
        for i in range(num_frames):
            t = i / num_frames
            # Belt marker moving along path
            belt_pos = pulley1_center + t * (pulley2_center - pulley1_center)
            belt_positions.append(belt_pos.tolist())
            
        return {
            "pulley1_center": pulley1_center.tolist(),
            "pulley2_center": pulley2_center.tolist(),
            "belt_positions": belt_positions
        }
        
    def generate_spring_simulation(self, params: Dict, key_points: Dict, num_frames: int) -> Dict:
        """스프링 시뮬레이션 데이터 생성"""
        
        anchor1 = np.array(key_points["anchor1"])
        anchor2 = np.array(key_points["anchor2"])
        rest_pos = np.array(key_points["mass_position"])
        
        mass_positions = []
        
        for i in range(num_frames):
            t = 2 * np.pi * i / num_frames
            # Simple harmonic motion
            displacement = 20 * np.sin(t)
            mass_pos = rest_pos + np.array([displacement, 0])
            mass_positions.append(mass_pos.tolist())
            
        return {
            "anchor1": anchor1.tolist(),
            "anchor2": anchor2.tolist(),
            "mass_positions": mass_positions
        }
        
    def test_mechanism_creation(self, mech_type: str, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """개별 메커니즘 생성 테스트"""
        
        logger.info(f"🔧 테스트 시작: {mech_type}")
        
        result = {
            "mechanism_type": mech_type,
            "success": False,
            "visual_count": 0,
            "expected_count": test_case["expected_visuals"],
            "animation_frames": 0,
            "errors": []
        }
        
        try:
            # 테스트 데이터 생성
            layer_data = self.create_test_mechanism_data(test_case)
            
            # 메커니즘 생성 시도
            scene_manager = self.mechanism_tab.scene_manager
            
            # 기존 메커니즘 제거
            scene_manager.clear_all_mechanisms()
            
            # 새 메커니즘 추가
            from automataii.ui.tabs.mechanism_design.visuals.visual_factory import create
            visual_items, debug_items = create(layer_data, scene_manager, is_preview=False)
            
            result["visual_count"] = len(visual_items)
            logger.info(f"  ✓ 비주얼 아이템 생성: {len(visual_items)}개 (예상: {test_case['expected_visuals']}개)")
            
            # 애니메이션 테스트
            if layer_data.get("full_simulation_data"):
                animation_frames = self.test_animation_frames(layer_data, visual_items)
                result["animation_frames"] = animation_frames
                logger.info(f"  ✓ 애니메이션 프레임 테스트: {animation_frames}개")
            
            # 성공 조건 확인
            if result["visual_count"] == result["expected_count"] and result["animation_frames"] > 0:
                result["success"] = True
                logger.info(f"  ✅ {mech_type} 테스트 성공!")
            else:
                logger.warning(f"  ⚠️ {mech_type} 테스트 부분 성공 (비주얼: {result['visual_count']}/{result['expected_count']}, 애니메이션: {result['animation_frames']})")
                
        except Exception as e:
            result["errors"].append(str(e))
            logger.error(f"  ❌ {mech_type} 테스트 실패: {e}")
            
        return result
        
    def test_animation_frames(self, layer_data: Dict, visual_items: List) -> int:
        """애니메이션 프레임 테스트"""
        
        if not visual_items:
            return 0
            
        try:
            from automataii.ui.tabs.mechanism_design.visuals.visual_factory import update
            from automataii.ui.tabs.mechanism_design.utils import get_scene_transform_function
            
            transform = get_scene_transform_function(layer_data)
            successful_frames = 0
            
            # 10개 프레임 테스트
            for i in range(10):
                time = 2 * np.pi * i / 10
                try:
                    update("test_mechanism", layer_data, time, visual_items)
                    successful_frames += 1
                except Exception as e:
                    logger.debug(f"    Frame {i} 업데이트 실패: {e}")
                    
            return successful_frames
            
        except Exception as e:
            logger.debug(f"    애니메이션 테스트 실패: {e}")
            return 0
            
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """종합 테스트 실행"""
        
        logger.info("🚀 메커니즘 시스템 종합 검증 시작")
        
        self.setup_application()
        
        overall_results = {
            "total_mechanisms": len(self.MECHANISM_TEST_CASES),
            "successful_mechanisms": 0,
            "partial_success": 0,
            "failed_mechanisms": 0,
            "individual_results": {},
            "summary": ""
        }
        
        # 각 메커니즘 타입 테스트
        for mech_type, test_case in self.MECHANISM_TEST_CASES.items():
            result = self.test_mechanism_creation(mech_type, test_case)
            overall_results["individual_results"][mech_type] = result
            
            if result["success"]:
                overall_results["successful_mechanisms"] += 1
            elif result["visual_count"] > 0 or result["animation_frames"] > 0:
                overall_results["partial_success"] += 1
            else:
                overall_results["failed_mechanisms"] += 1
                
        # 결과 요약
        summary = f"""
📊 메커니즘 시스템 검증 결과:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 완전 성공: {overall_results['successful_mechanisms']}/{overall_results['total_mechanisms']}
⚠️  부분 성공: {overall_results['partial_success']}/{overall_results['total_mechanisms']}
❌ 실패: {overall_results['failed_mechanisms']}/{overall_results['total_mechanisms']}

상세 결과:
"""
        
        for mech_type, result in overall_results["individual_results"].items():
            status = "✅" if result["success"] else "⚠️" if (result["visual_count"] > 0 or result["animation_frames"] > 0) else "❌"
            summary += f"{status} {mech_type}: 비주얼 {result['visual_count']}/{result['expected_count']}, 애니메이션 {result['animation_frames']}프레임\n"
            
        overall_results["summary"] = summary
        
        logger.info(summary)
        
        return overall_results
        
    def cleanup(self):
        """리소스 정리"""
        if self.main_window:
            self.main_window.close()
        if self.app:
            self.app.quit()


def main():
    """메인 실행 함수"""
    
    tester = MechanismVerificationTester()
    
    try:
        results = tester.run_comprehensive_test()
        
        # 결과 파일 저장
        import json
        results_file = Path(__file__).parent / "mechanism_verification_results.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
            
        logger.info(f"📁 결과 저장됨: {results_file}")
        
        # 성공률 체크
        success_rate = results["successful_mechanisms"] / results["total_mechanisms"]
        if success_rate >= 0.8:
            logger.info("🎉 메커니즘 시스템 검증 통과! (80% 이상 성공)")
            return 0
        else:
            logger.warning(f"⚠️ 메커니즘 시스템 검증 부분 실패 (성공률: {success_rate:.1%})")
            return 1
            
    except Exception as e:
        logger.error(f"💥 검증 과정에서 치명적 오류 발생: {e}")
        return 2
        
    finally:
        tester.cleanup()


if __name__ == "__main__":
    sys.exit(main())