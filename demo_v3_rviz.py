#!/usr/bin/env python3
"""
PIPER 로봇 RViz 시각화 버전 v3
- 안전한 종료 시스템
- 좌측 카메라 최적화
- RViz 실시간 시각화
- ROS joint_states 및 tf 브로드캐스트
"""

import cv2
import numpy as np
import pyrealsense2 as rs
import mediapipe as mp
import time
import sys
import math
import signal
import atexit
from collections import deque

# PIPER SDK
from piper_sdk import *

# ROS (Noetic - Ubuntu 20.04)
try:
    import rospy
    from sensor_msgs.msg import JointState
    from std_msgs.msg import Header
    import tf2_ros
    import tf_conversions
    from geometry_msgs.msg import TransformStamped
    ROS_AVAILABLE = True
    print("✅ ROS Noetic 모듈 로드 성공")
except ImportError:
    ROS_AVAILABLE = False
    print("⚠️  ROS 없음 - 시각화 비활성화")


class SafePiperTeleoperation:
    """안전한 PIPER 텔레오퍼레이션 with RViz"""
    
    def __init__(self, enable_rviz=True):
        """초기화"""
        print("\n" + "=" * 70)
        print("   🛡️  PIPER 안전 제어 + RViz v3")
        print("   ✋ 좌측 카메라 최적화 + 실시간 시각화")
        print("   📷 Intel RealSense D435I")
        print("=" * 70 + "\n")
        
        # RViz 활성화 여부
        self.enable_rviz = enable_rviz and ROS_AVAILABLE
        
        # ROS 초기화
        if self.enable_rviz:
            self.initialize_ros()
        
        # 안전 종료 플래그
        self.shutdown_in_progress = False
        self.emergency_shutdown = False
        
        # PIPER 로봇 초기화
        self.piper = None
        self.initialize_robot()
        
        # RealSense 초기화
        self.initialize_camera()
        
        # MediaPipe 초기화
        self.initialize_mediapipe()
        
        # 작업 공간
        self.workspace = {
            'x_min': -0.5, 'x_max': 0.5,
            'y_min': -0.3, 'y_max': 0.3,
            'z_min': 0.1, 'z_max': 0.5
        }
        
        # 홈 포지션 Z축 하한선
        self.home_z_limit = 0.25
        
        # 캘리브레이션
        self.is_calibrated = False
        self.hand_home_pos = None
        self.hand_home_orient = None
        self.robot_home_pos = np.array([0.35, 0.0, 0.3])
        self.robot_home_orient = np.array([0.0, math.pi, 0.0])
        
        # 제어 파라미터
        self.pos_scale = 1.0
        self.orient_scale = 0.5
        self.pos_smooth = 0.3
        self.orient_smooth = 0.4
        
        # NumPy 배열로 초기화
        self.prev_position = np.array(self.robot_home_pos)
        self.prev_orientation = np.array(self.robot_home_orient)
        
        # 상태
        self.is_running = True
        self.gripper_open = True
        self.control_enabled = False
        
        # 성능
        self.last_command_time = 0
        self.command_interval = 0.05
        
        # Signal handler
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        atexit.register(self.emergency_cleanup)
        
        print("\n✅ 시스템 준비 완료!")
        if self.enable_rviz:
            print("📊 RViz 시각화 활성화")
            print("   터미널에서 실행: roslaunch piper_description display.launch")
            print("   또는: rviz -d config/piper.rviz")
        print("🛡️  안전 기능 활성화\n")
    
    def initialize_ros(self):
        """ROS Noetic 초기화"""
        try:
            rospy.init_node('piper_teleoperation', anonymous=True)
            
            # Joint state publisher
            self.joint_pub = rospy.Publisher(
                '/joint_states',
                JointState,
                queue_size=10
            )
            
            # TF2 broadcaster (Noetic 권장)
            self.tf_broadcaster = tf2_ros.TransformBroadcaster()
            
            # Static TF broadcaster (world -> base_link)
            self.static_tf_broadcaster = tf2_ros.StaticTransformBroadcaster()
            
            # Static transform 발행
            static_transform = TransformStamped()
            static_transform.header.stamp = rospy.Time.now()
            static_transform.header.frame_id = "world"
            static_transform.child_frame_id = "base_link"
            static_transform.transform.translation.x = 0.0
            static_transform.transform.translation.y = 0.0
            static_transform.transform.translation.z = 0.0
            static_transform.transform.rotation.x = 0.0
            static_transform.transform.rotation.y = 0.0
            static_transform.transform.rotation.z = 0.0
            static_transform.transform.rotation.w = 1.0
            self.static_tf_broadcaster.sendTransform(static_transform)
            
            # Joint names
            self.joint_names = [
                'joint_1',
                'joint_2', 
                'joint_3',
                'joint_4',
                'joint_5',
                'joint_6',
                'gripper_joint'
            ]
            
            print("✅ ROS Noetic 초기화 완료")
            
        except Exception as e:
            print(f"⚠️  ROS 초기화 실패: {e}")
            self.enable_rviz = False
    
    def publish_robot_state(self):
        """로봇 상태를 ROS로 publish (Noetic tf2)"""
        if not self.enable_rviz or not self.piper:
            return
        
        try:
            # 관절 상태 가져오기
            joint_msg = self.piper.GetArmJointMsgs()
            gripper_msg = self.piper.GetArmGripperMsgs()
            end_pose = self.piper.GetArmEndPoseMsgs()
            
            # Joint state 메시지 생성
            js_msg = JointState()
            js_msg.header = Header()
            js_msg.header.stamp = rospy.Time.now()
            js_msg.name = self.joint_names
            
            # 관절 각도 (PIPER는 mdeg 단위)
            js_msg.position = [
                math.radians(joint_msg.joint_state.joint_1 / 1000.0),
                math.radians(joint_msg.joint_state.joint_2 / 1000.0),
                math.radians(joint_msg.joint_state.joint_3 / 1000.0),
                math.radians(joint_msg.joint_state.joint_4 / 1000.0),
                math.radians(joint_msg.joint_state.joint_5 / 1000.0),
                math.radians(joint_msg.joint_state.joint_6 / 1000.0),
                gripper_msg.gripper_state.grippers_angle / 1000000.0  # μm → m
            ]
            
            # Publish joint states
            self.joint_pub.publish(js_msg)
            
            # TF2 브로드캐스트 (base_link → end_effector)
            # End effector 위치 (μm → m)
            x = end_pose.end_pose.X_axis / 1000000.0
            y = end_pose.end_pose.Y_axis / 1000000.0
            z = end_pose.end_pose.Z_axis / 1000000.0
            
            # 자세 (mdeg → rad)
            rx = math.radians(end_pose.end_pose.RX_axis / 1000.0)
            ry = math.radians(end_pose.end_pose.RY_axis / 1000.0)
            rz = math.radians(end_pose.end_pose.RZ_axis / 1000.0)
            
            # Euler to Quaternion (tf_conversions)
            quat = tf_conversions.transformations.quaternion_from_euler(rx, ry, rz)
            
            # TF2 Transform 메시지
            t = TransformStamped()
            t.header.stamp = rospy.Time.now()
            t.header.frame_id = "base_link"
            t.child_frame_id = "end_effector"
            t.transform.translation.x = x
            t.transform.translation.y = y
            t.transform.translation.z = z
            t.transform.rotation.x = quat[0]
            t.transform.rotation.y = quat[1]
            t.transform.rotation.z = quat[2]
            t.transform.rotation.w = quat[3]
            
            # TF2 브로드캐스트
            self.tf_broadcaster.sendTransform(t)
            
        except Exception as e:
            pass  # ROS 에러는 조용히 무시
    
    def signal_handler(self, signum, frame):
        """Signal handler"""
        print("\n\n⚠️  중단 신호 감지! 안전 종료 시작...")
        self.emergency_shutdown = True
        self.is_running = False
    
    def emergency_cleanup(self):
        """비상 정리"""
        if self.shutdown_in_progress:
            return
        
        if self.emergency_shutdown and self.piper:
            print("\n🚨 비상 종료 모드")
            self.safe_shutdown()
    
    def initialize_robot(self):
        """로봇 초기화"""
        print("PIPER 로봇 연결 중...")
        try:
            self.piper = C_PiperInterface("can0")
            time.sleep(0.2)
            
            self.piper.ConnectPort()
            time.sleep(0.5)
            print("✅ PIPER CAN 연결 성공")
            
            print("🔧 로봇 암 활성화 중...")
            self.piper.EnableArm(7)
            time.sleep(1.0)
            
            enable_status = self.piper.GetArmEnableStatus()
            if all(enable_status):
                print("✅ 로봇 암 활성화 완료")
            
            print("🔧 제어 모드 설정 중...")
            self.piper.ModeCtrl(
                ctrl_mode=0x01,
                move_mode=0x00,
                move_spd_rate_ctrl=50,
                is_mit_mode=0x00
            )
            time.sleep(0.3)
            print("✅ 제어 모드 설정 완료")
            
            print("🔧 그리퍼 초기화 중...")
            self.piper.GripperCtrl(
                gripper_angle=50000,
                gripper_effort=1000,
                gripper_code=0x03,
                set_zero=0x00
            )
            time.sleep(0.5)
            print("✅ 그리퍼 초기화 완료")
            
            print("🏠 홈 포지션으로 이동 중...")
            self.move_to_home_position()
            
            # Z축 하한선 저장
            try:
                end_pose = self.piper.GetArmEndPoseMsgs()
                self.home_z_limit = end_pose.end_pose.Z_axis / 1000000
                print(f"🛡️  Z축 안전 하한선: {self.home_z_limit:.3f}m")
            except:
                self.home_z_limit = 0.25
            
            print("✅ 초기화 완료!")
            
        except Exception as e:
            print(f"❌ PIPER 초기화 실패: {e}")
            import traceback
            traceback.print_exc()
            self.piper = None
    
    def initialize_camera(self):
        """카메라 초기화"""
        print("\n📷 RealSense 카메라 초기화...")
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        self.config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        self.config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        
        try:
            self.profile = self.pipeline.start(self.config)
            depth_sensor = self.profile.get_device().first_depth_sensor()
            self.depth_scale = depth_sensor.get_depth_scale()
            self.align = rs.align(rs.stream.color)
            print("✅ RealSense 준비 완료")
        except Exception as e:
            print(f"❌ RealSense 오류: {e}")
            sys.exit(1)
    
    def initialize_mediapipe(self):
        """MediaPipe 초기화"""
        print("🖐️  MediaPipe Hands 초기화...")
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        print("✅ MediaPipe 준비 완료")
    
    def move_to_home_position(self):
        """홈 포지션으로 이동 (기존 동작 중단)"""
        if not self.piper:
            return
        
        try:
            # 1. 제어 즉시 중지
            print("⏸️  제어 중지...")
            self.control_enabled = False
            time.sleep(0.1)
            
            # 2. 현재 동작 정지
            print("🛑 현재 동작 정지...")
            try:
                end_pose = self.piper.GetArmEndPoseMsgs()
                self.piper.EndPoseCtrl(
                    end_pose.end_pose.X_axis,
                    end_pose.end_pose.Y_axis,
                    end_pose.end_pose.Z_axis,
                    end_pose.end_pose.RX_axis,
                    end_pose.end_pose.RY_axis,
                    end_pose.end_pose.RZ_axis
                )
                time.sleep(0.3)
            except:
                pass
            
            # 3. MOVE J 모드
            print("🏠 홈 포지션으로 이동 시작...")
            self.piper.ModeCtrl(
                ctrl_mode=0x01,
                move_mode=0x01,
                move_spd_rate_ctrl=30,
                is_mit_mode=0x00
            )
            time.sleep(0.2)
            
            # 4. 홈 포지션
            self.piper.JointCtrl(
                joint_1=0,
                joint_2=0,
                joint_3=0,
                joint_4=0,
                joint_5=0,
                joint_6=0
            )
            time.sleep(2.0)
            
            # 5. MOVE P 복귀
            self.piper.ModeCtrl(
                ctrl_mode=0x01,
                move_mode=0x00,
                move_spd_rate_ctrl=50,
                is_mit_mode=0x00
            )
            time.sleep(0.2)
            
            print("✅ 홈 포지션 도착!")
            
        except Exception as e:
            print(f"⚠️  홈 포지션 이동 실패: {e}")
    
    def get_hand_3d_position(self, hand_landmarks, depth_frame, intrinsics):
        """손목 3D 위치"""
        wrist = hand_landmarks.landmark[self.mp_hands.HandLandmark.WRIST]
        h, w = depth_frame.shape
        x_pixel = int(np.clip(wrist.x * w, 0, w - 1))
        y_pixel = int(np.clip(wrist.y * h, 0, h - 1))
        
        depth = depth_frame[y_pixel, x_pixel] * self.depth_scale
        if depth == 0:
            region = depth_frame[max(0, y_pixel-5):min(h, y_pixel+5),
                                max(0, x_pixel-5):min(w, x_pixel+5)]
            depth = np.mean(region[region > 0]) * self.depth_scale if np.any(region > 0) else 0
        
        if depth > 0:
            point_3d = rs.rs2_deproject_pixel_to_point(intrinsics, [x_pixel, y_pixel], depth)
            return np.array(point_3d)
        return None
    
    def calculate_hand_orientation(self, hand_landmarks, depth_frame, intrinsics):
        """손 자세 계산"""
        try:
            wrist = hand_landmarks.landmark[self.mp_hands.HandLandmark.WRIST]
            middle_mcp = hand_landmarks.landmark[self.mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
            index_mcp = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_MCP]
            
            h, w = depth_frame.shape
            
            def get_3d_point(landmark):
                x_pixel = int(np.clip(landmark.x * w, 0, w - 1))
                y_pixel = int(np.clip(landmark.y * h, 0, h - 1))
                depth = depth_frame[y_pixel, x_pixel] * self.depth_scale
                if depth == 0:
                    region = depth_frame[max(0, y_pixel-5):min(h, y_pixel+5),
                                        max(0, x_pixel-5):min(w, x_pixel+5)]
                    depth = np.mean(region[region > 0]) * self.depth_scale if np.any(region > 0) else 0
                if depth > 0:
                    return np.array(rs.rs2_deproject_pixel_to_point(intrinsics, [x_pixel, y_pixel], depth))
                return None
            
            wrist_3d = get_3d_point(wrist)
            middle_3d = get_3d_point(middle_mcp)
            index_3d = get_3d_point(index_mcp)
            
            if wrist_3d is None or middle_3d is None or index_3d is None:
                return None
            
            hand_forward = middle_3d - wrist_3d
            hand_right = index_3d - middle_3d
            
            hand_forward = hand_forward / (np.linalg.norm(hand_forward) + 1e-6)
            hand_right = hand_right / (np.linalg.norm(hand_right) + 1e-6)
            
            pitch = math.atan2(-hand_forward[1], math.sqrt(hand_forward[0]**2 + hand_forward[2]**2))
            yaw = math.atan2(hand_forward[0], hand_forward[2])
            roll = math.atan2(hand_right[1], hand_right[0])
            
            return np.array([roll, pitch, yaw])
            
        except:
            return None
    
    def calculate_finger_distance(self, hand_landmarks):
        """손가락 간격"""
        try:
            thumb_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_TIP]
            index_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
            
            dx = thumb_tip.x - index_tip.x
            dy = thumb_tip.y - index_tip.y
            distance = math.sqrt(dx**2 + dy**2)
            
            return distance
        except:
            return None
    
    def calibrate(self, hand_pos, hand_orient):
        """캘리브레이션"""
        self.hand_home_pos = hand_pos.copy()
        self.hand_home_orient = hand_orient.copy()
        self.is_calibrated = True
        print(f"✅ 캘리브레이션 완료!")
    
    def hand_to_robot_pose(self, hand_pos, hand_orient):
        """손 → 로봇 좌표 변환 (좌측 카메라)"""
        if not self.is_calibrated or self.hand_home_pos is None:
            return None, None
        
        hand_delta = hand_pos - self.hand_home_pos
        orient_delta = hand_orient - self.hand_home_orient
        
        # 좌측 카메라 매핑
        robot_delta = np.array([
            -hand_delta[0],  # X (좌우) → X (전후, 반전)
            hand_delta[2],   # Z (Depth) → Y (좌우)
            hand_delta[1]    # Y (상하) → Z (상하)
        ])
        
        target_pos = self.robot_home_pos + robot_delta * self.pos_scale
        target_pos = np.clip(target_pos, 
                           [self.workspace['x_min'], self.workspace['y_min'], self.workspace['z_min']],
                           [self.workspace['x_max'], self.workspace['y_max'], self.workspace['z_max']])
        
        # Z축 안전 하한선
        target_pos[2] = max(target_pos[2], self.home_z_limit)
        
        # Depth → Yaw 회전
        yaw_from_depth = hand_delta[2] * 2.0
        
        target_orient = np.array(self.robot_home_orient).copy()
        target_orient[0] += orient_delta[0] * self.orient_scale
        target_orient[1] += orient_delta[1] * self.orient_scale
        target_orient[2] += yaw_from_depth
        
        # 스무딩
        target_pos = np.array(self.prev_position) * (1 - self.pos_smooth) + np.array(target_pos) * self.pos_smooth
        target_orient = np.array(self.prev_orientation) * (1 - self.orient_smooth) + np.array(target_orient) * self.orient_smooth
        
        self.prev_position = np.array(target_pos)
        self.prev_orientation = np.array(target_orient)
        
        return target_pos, target_orient
    
    def send_robot_command(self, position, orientation, finger_distance=None):
        """로봇 명령 전송"""
        if not self.piper:
            return
        
        current_time = time.time()
        if current_time - self.last_command_time < self.command_interval:
            return
        
        try:
            X = int(round(position[0] * 1000 * 1000))
            Y = int(round(position[1] * 1000 * 1000))
            Z = int(round(position[2] * 1000 * 1000))
            
            RX = int(round(math.degrees(orientation[0]) * 1000))
            RY = int(round(math.degrees(orientation[1]) * 1000))
            RZ = int(round(math.degrees(orientation[2]) * 1000))
            
            self.piper.EndPoseCtrl(X, Y, Z, RX, RY, RZ)
            
            if finger_distance is not None:
                gripper_angle = int(np.interp(finger_distance, [0.0, 0.3], [10000, 80000]))
                gripper_angle = np.clip(gripper_angle, 10000, 80000)
                
                self.piper.GripperCtrl(
                    gripper_angle=gripper_angle,
                    gripper_effort=1000,
                    gripper_code=0x01,
                    set_zero=0x00
                )
            
            self.last_command_time = current_time
            
        except Exception as e:
            pass
    
    def safe_shutdown(self):
        """안전 종료"""
        if self.shutdown_in_progress or not self.piper:
            return
        
        self.shutdown_in_progress = True
        print("\n🛡️  안전 종료 시퀀스 시작...")
        
        try:
            self.control_enabled = False
            time.sleep(0.2)
            
            print("🖐️  그리퍼 열기...")
            self.piper.GripperCtrl(
                gripper_angle=80000,
                gripper_effort=500,
                gripper_code=0x01,
                set_zero=0x00
            )
            time.sleep(0.5)
            
            print("🏠 홈 포지션으로 복귀 중...")
            self.piper.ModeCtrl(
                ctrl_mode=0x01,
                move_mode=0x01,
                move_spd_rate_ctrl=20,
                is_mit_mode=0x00
            )
            time.sleep(0.3)
            
            self.piper.JointCtrl(
                joint_1=0,
                joint_2=0,
                joint_3=0,
                joint_4=0,
                joint_5=0,
                joint_6=0
            )
            print("⏳ 이동 완료 대기 중... (3초)")
            time.sleep(3.0)
            
            print("😴 대기 모드로 전환...")
            self.piper.ModeCtrl(0x00, 0x01, 10, 0x00)
            time.sleep(0.5)
            
            print("🔓 토크 해제 (리셋)...")
            self.piper.ResetPiper()
            time.sleep(0.5)
            
            self.piper.DisconnectPort()
            print("✅ 안전 종료 완료!")
            
        except Exception as e:
            print(f"⚠️  안전 종료 중 오류: {e}")
            try:
                self.piper.ResetPiper()
                time.sleep(0.3)
                self.piper.DisconnectPort()
            except:
                pass
    
    def draw_ui(self, image, hand_pos, robot_pos, finger_dist):
        """UI 그리기"""
        h, w, _ = image.shape
        
        overlay = image.copy()
        cv2.rectangle(overlay, (10, 10), (w-10, 220), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.65, image, 0.35, 0, image)
        
        # 제목
        title = "PIPER RViz v3" if self.enable_rviz else "PIPER Safe v3"
        cv2.putText(image, title, (20, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        
        # 로봇 상태
        status = "Connected" if self.piper else "Disconnected"
        color = (0, 255, 0) if self.piper else (0, 0, 255)
        cv2.putText(image, f"Robot: {status}", (20, 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # RViz 상태
        if self.enable_rviz:
            cv2.putText(image, "RViz: Active", (20, 95),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # 제어 상태
        y_offset = 120
        if self.control_enabled:
            status_text = "ACTIVE"
            status_color = (0, 255, 0)
        elif self.is_calibrated:
            status_text = "PAUSED (Press SPACE)"
            status_color = (0, 165, 255)
        else:
            status_text = "Press [C] to Calibrate"
            status_color = (0, 0, 255)
        cv2.putText(image, f"Control: {status_text}", (20, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 2)
        
        y_offset += 25
        cv2.putText(image, f"Z-Limit: {self.home_z_limit:.3f}m", (20, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        
        y_offset += 25
        if hand_pos is not None:
            cv2.putText(image, f"Hand: X={hand_pos[0]:.2f} Y={hand_pos[1]:.2f} Z={hand_pos[2]:.2f}",
                       (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
            y_offset += 25
        
        if finger_dist is not None:
            cv2.putText(image, f"Finger: {finger_dist:.3f}", (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 0), 1)
        
        cv2.putText(image, "[C]alibrate [SPACE]On/Off [H]ome [Q]uit", (10, h-20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    
    def run(self):
        """메인 루프"""
        try:
            color_profile = self.profile.get_stream(rs.stream.color)
            intrinsics = color_profile.as_video_stream_profile().get_intrinsics()
            
            print("▶️  프로그램 시작!\n")
            
            while self.is_running:
                if self.emergency_shutdown:
                    break
                
                frames = self.pipeline.wait_for_frames()
                aligned = self.align.process(frames)
                depth_frame = aligned.get_depth_frame()
                color_frame = aligned.get_color_frame()
                
                if not depth_frame or not color_frame:
                    continue
                
                depth_image = np.asanyarray(depth_frame.get_data())
                color_image = np.asanyarray(color_frame.get_data())
                rgb_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
                
                results = self.hands.process(rgb_image)
                
                hand_pos = None
                robot_pos = None
                finger_dist = None
                
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        self.mp_draw.draw_landmarks(
                            color_image, hand_landmarks, self.mp_hands.HAND_CONNECTIONS,
                            self.mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3),
                            self.mp_draw.DrawingSpec(color=(255, 0, 0), thickness=2)
                        )
                        
                        hand_pos = self.get_hand_3d_position(hand_landmarks, depth_image, intrinsics)
                        hand_orient = self.calculate_hand_orientation(hand_landmarks, depth_image, intrinsics)
                        finger_dist = self.calculate_finger_distance(hand_landmarks)
                        
                        if hand_pos is not None and hand_orient is not None:
                            robot_pos, robot_orient = self.hand_to_robot_pose(hand_pos, hand_orient)
                            
                            if self.control_enabled and robot_pos is not None:
                                self.send_robot_command(robot_pos, robot_orient, finger_dist)
                
                # RViz 업데이트
                if self.enable_rviz:
                    self.publish_robot_state()
                
                self.draw_ui(color_image, hand_pos, robot_pos, finger_dist)
                cv2.imshow('PIPER RViz Control', color_image)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\n👋 정상 종료 요청...")
                    self.is_running = False
                elif key == ord('c') and hand_pos is not None and hand_orient is not None:
                    self.calibrate(hand_pos, hand_orient)
                elif key == ord(' '):
                    if self.is_calibrated:
                        self.control_enabled = not self.control_enabled
                        print(f"🎮 제어: {'활성화 ✅' if self.control_enabled else '일시정지 ⏸️'}")
                elif key == ord('h'):
                    print("🏠 홈 포지션으로 이동...")
                    self.move_to_home_position()
        
        except KeyboardInterrupt:
            print("\n⚠️  KeyboardInterrupt")
            self.emergency_shutdown = True
        except Exception as e:
            print(f"\n❌ 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """정리"""
        if self.shutdown_in_progress:
            return
        
        print("\n🧹 시스템 종료 중...")
        
        if self.piper:
            self.safe_shutdown()
        
        try:
            self.pipeline.stop()
        except:
            pass
        
        cv2.destroyAllWindows()
        
        try:
            self.hands.close()
        except:
            pass
        
        if self.enable_rviz:
            try:
                rospy.signal_shutdown("User terminated")
            except:
                pass
        
        print("✅ 종료 완료")


def main():
    """메인"""
    import argparse
    parser = argparse.ArgumentParser(description='PIPER Teleoperation with RViz')
    parser.add_argument('--no-rviz', action='store_true', help='Disable RViz visualization')
    args = parser.parse_args()
    
    try:
        teleop = SafePiperTeleoperation(enable_rviz=not args.no_rviz)
        teleop.run()
    except Exception as e:
        print(f"\n❌ 프로그램 오류: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
