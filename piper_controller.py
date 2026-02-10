#!/usr/bin/env python3
"""
PIPER 로봇 SDK 인터페이스
ROS 메시지를 PIPER SDK 명령으로 변환
"""

import rospy
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Float32
try:
    from piper_sdk import C_PiperInterface  # PIPER SDK
except ImportError:
    print("⚠️  PIPER SDK를 찾을 수 없습니다. 시뮬레이션 모드로 실행합니다.")
    C_PiperInterface = None


class PiperController:
    def __init__(self):
        """PIPER 컨트롤러 초기화"""
        rospy.init_node('piper_controller', anonymous=True)
        
        # PIPER SDK 초기화
        self.piper = None
        if C_PiperInterface:
            try:
                self.piper = C_PiperInterface()
                self.piper.ConnectPort()
                print("✅ PIPER 로봇 연결 성공")
            except Exception as e:
                print(f"❌ PIPER 연결 실패: {e}")
                self.piper = None
        
        # ROS Subscribers
        rospy.Subscriber('/piper/target_pose', PoseStamped, self.pose_callback)
        rospy.Subscriber('/piper/gripper', Float32, self.gripper_callback)
        
        # 제어 주파수
        self.rate = rospy.Rate(30)  # 30Hz
        
        print("✅ PIPER 컨트롤러 초기화 완료")
    
    def pose_callback(self, msg):
        """타겟 포즈 명령 수신"""
        x = msg.pose.position.x
        y = msg.pose.position.y
        z = msg.pose.position.z
        
        # 오리엔테이션 (Quaternion to Euler if needed)
        # 현재는 고정된 자세 사용
        roll, pitch, yaw = 0.0, 0.0, 0.0
        
        if self.piper:
            try:
                # PIPER SDK의 역기구학(IK) 함수 호출
                # 실제 API는 PIPER SDK 문서 참조
                self.piper.MotionCtrl_1(0x00, 0x01, x*1000, y*1000, z*1000)  # mm 단위
                rospy.logdebug(f"Target pose: x={x:.3f}, y={y:.3f}, z={z:.3f}")
            except Exception as e:
                rospy.logerr(f"PIPER 제어 오류: {e}")
        else:
            # 시뮬레이션 모드
            rospy.loginfo(f"[SIM] Target: x={x:.3f}, y={y:.3f}, z={z:.3f}")
    
    def gripper_callback(self, msg):
        """그리퍼 명령 수신"""
        gripper_value = msg.data  # 0.0 (닫힘) ~ 1.0 (열림)
        
        if self.piper:
            try:
                # PIPER SDK의 그리퍼 제어 함수
                gripper_pos = int(gripper_value * 1000)  # 0 ~ 1000 범위로 변환
                self.piper.GripperCtrl(gripper_pos, 500)  # (위치, 속도)
                rospy.logdebug(f"Gripper: {gripper_value:.2f}")
            except Exception as e:
                rospy.logerr(f"그리퍼 제어 오류: {e}")
        else:
            # 시뮬레이션 모드
            status = "OPEN" if gripper_value > 0.5 else "CLOSED"
            rospy.loginfo(f"[SIM] Gripper: {status}")
    
    def run(self):
        """메인 루프"""
        rospy.loginfo("PIPER 컨트롤러 실행 중...")
        
        try:
            while not rospy.is_shutdown():
                self.rate.sleep()
        except KeyboardInterrupt:
            rospy.loginfo("사용자에 의해 중단됨")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """리소스 정리"""
        if self.piper:
            try:
                # 로봇을 안전한 위치로 이동
                self.piper.GripperCtrl(1000, 500)  # 그리퍼 열기
                rospy.sleep(0.5)
                # self.piper.MotionCtrl_HomePos()  # 홈 위치로 이동
                self.piper.DisConnectPort()
                print("✅ PIPER 연결 해제")
            except Exception as e:
                print(f"정리 중 오류: {e}")


def main():
    """메인 함수"""
    print("=" * 60)
    print("   PIPER 로봇 컨트롤러")
    print("=" * 60)
    
    controller = PiperController()
    controller.run()


if __name__ == "__main__":
    main()
