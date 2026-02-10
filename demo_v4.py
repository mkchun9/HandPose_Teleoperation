#!/usr/bin/env python3
# -*-coding:utf8-*-
"""
Piper Robot Hand Gesture Control System - Fixed Version
- Uses actual robot coordinate system (micrometers)
- Fixed gripper orientation pointing downward
- Direct pixel-to-robot position mapping
"""

import time
import cv2
import numpy as np
import pyrealsense2 as rs
import mediapipe as mp
from piper_sdk import *
import threading
from collections import deque

class PiperHandControl:
    def __init__(self, can_port="can0"):
        # Piper 로봇 초기화
        self.piper = C_PiperInterface_V2(can_port)
        self.piper.ConnectPort()
        while not self.piper.EnablePiper():
            time.sleep(0.01)
        
        # RealSense 카메라 초기화
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        self.config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        self.config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        self.pipeline.start(self.config)
        
        # Align depth to color
        self.align = rs.align(rs.stream.color)
        
        # MediaPipe 손 감지 초기화
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        # 제어 상태
        self.is_controlling = False
        self.is_initialized = False
        
        # ===== 실제 로봇 좌표 (마이크로미터 단위) =====
        # START 위치 - 로봇이 보고한 실제 위치 사용
        self.start_position = {
            'X': 304611,      # 마이크로미터
            'Y': -9565,       # 마이크로미터
            'Z': 144558,      # 마이크로미터
            'RX': -169105,    # 마이크로미터 (각도 * 1000)
            'RY': -3956,      # 마이크로미터 (각도 * 1000) - 그리퍼 방향
            'RZ': 124014      # 마이크로미터 (각도 * 1000)
        }
        
        # 그리퍼 방향 고정 (START 위치의 방향 그대로 유지)
        self.fixed_orientation = {
            'RX': -169105,
            'RY': -3956,
            'RZ': 124014
        }
        
        # 현재 로봇 위치 (마이크로미터)
        self.current_robot_pos = self.start_position.copy()
        
        # 초기 손목 위치 (픽셀 좌표 및 depth)
        self.init_wrist_pixel = None  # (x, y)
        self.init_wrist_depth = None  # mm
        
        # ===== 제어 파라미터 =====
        # 픽셀 1개 움직임 = 로봇 N 마이크로미터 움직임
        self.pixel_to_um_x = 300      # X축: 픽셀당 300um (0.3mm)
        self.pixel_to_um_y = 300      # Y축: 픽셀당 300um (0.3mm) - 상하
        self.pixel_to_um_z = 500      # Z축: depth 1mm당 500um (0.5mm) - 전후
        
        # 안전 구역 설정 (마이크로미터 단위)
        # START 위치 기준으로 ±100mm 정도 범위
        self.safety_zone = {
            'x_min': self.start_position['X'] - 250000,  # -100mm
            'x_max': self.start_position['X'] + 250000,  # +100mm
            'y_min': self.start_position['Y'] - 250000,  # -100mm
            'y_max': self.start_position['Y'] + 250000,  # +100mm
            'z_min': self.start_position['Z'] - 300000,  # -100mm
            'z_max': self.start_position['Z'] + 200000   # +100mm
        }
        
        # 그리퍼 제어
        self.gripper_open = 1000      # 완전히 열림
        self.gripper_closed = 0       # 완전히 닫힘
        self.current_gripper = self.gripper_open
        
        # 부드러운 제어를 위한 이동 평균 필터
        self.position_buffer = deque(maxlen=5)
        self.gripper_buffer = deque(maxlen=3)
        
        # 제어 루프 스레드
        self.control_thread = None
        self.running = False
        self.shutdown_in_progress = False
        self.control_enabled = False  # A 키로 제어 활성화
        
        # 픽셀 거리 -> 그리퍼 매핑 파라미터
        self.finger_dist_open = 100   # 픽셀, 손가락 완전히 벌렸을 때
        self.finger_dist_closed = 20  # 픽셀, 손가락 붙였을 때
        
    def get_hand_landmarks(self, frame):
        """손 랜드마크 추출"""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)
        
        if results.multi_hand_landmarks:
            return results.multi_hand_landmarks[0]
        return None
    
    def get_wrist_position(self, hand_landmarks, depth_frame, color_frame):
        """손목 위치 추출 (픽셀 좌표 및 depth)"""
        h, w, _ = color_frame.shape
        
        # 손목 (landmark 0)
        wrist = hand_landmarks.landmark[self.mp_hands.HandLandmark.WRIST]
        wrist_x = int(wrist.x * w)
        wrist_y = int(wrist.y * h)
        
        # Depth 값 가져오기 (mm 단위)
        wrist_depth = depth_frame.get_distance(wrist_x, wrist_y) * 1000
        
        return (wrist_x, wrist_y), wrist_depth
    
    def get_finger_distance(self, hand_landmarks, frame):
        """엄지와 검지 끝의 픽셀 거리 계산"""
        h, w, _ = frame.shape
        
        # 엄지 끝 (landmark 4)
        thumb_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_TIP]
        thumb_x = int(thumb_tip.x * w)
        thumb_y = int(thumb_tip.y * h)
        
        # 검지 끝 (landmark 8)
        index_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
        index_x = int(index_tip.x * w)
        index_y = int(index_tip.y * h)
        
        # 유클리드 거리
        distance = np.sqrt((thumb_x - index_x)**2 + (thumb_y - index_y)**2)
        
        return distance, (thumb_x, thumb_y), (index_x, index_y)
    
    def map_finger_to_gripper(self, finger_distance):
        """손가락 거리를 그리퍼 값으로 매핑"""
        # 거리를 0~1로 정규화
        normalized = (finger_distance - self.finger_dist_closed) / \
                     (self.finger_dist_open - self.finger_dist_closed)
        normalized = np.clip(normalized, 0, 1)
        
        # 그리퍼 값으로 변환
        gripper_value = int(self.gripper_closed + 
                           (self.gripper_open - self.gripper_closed) * normalized)
        
        return gripper_value
    
    def apply_safety_zone(self, pos_dict):
        """안전 구역 내로 위치 제한"""
        pos_dict['X'] = int(np.clip(pos_dict['X'], 
                                    self.safety_zone['x_min'], 
                                    self.safety_zone['x_max']))
        pos_dict['Y'] = int(np.clip(pos_dict['Y'], 
                                    self.safety_zone['y_min'], 
                                    self.safety_zone['y_max']))
        pos_dict['Z'] = int(np.clip(pos_dict['Z'], 
                                    self.safety_zone['z_min'], 
                                    self.safety_zone['z_max']))
        return pos_dict
    
    def smooth_position(self, new_pos_dict):
        """이동 평균을 사용한 위치 스무딩"""
        self.position_buffer.append([new_pos_dict['X'], new_pos_dict['Y'], new_pos_dict['Z']])
        if len(self.position_buffer) > 0:
            smoothed = np.mean(self.position_buffer, axis=0)
            new_pos_dict['X'] = int(smoothed[0])
            new_pos_dict['Y'] = int(smoothed[1])
            new_pos_dict['Z'] = int(smoothed[2])
        return new_pos_dict
    
    def smooth_gripper(self, new_gripper):
        """그리퍼 값 스무딩"""
        self.gripper_buffer.append(new_gripper)
        if len(self.gripper_buffer) > 0:
            return int(np.mean(self.gripper_buffer))
        return new_gripper
    
    def move_to_home(self):
        """Home 위치로 이동 (Joint Control)"""
        print("Moving to HOME position...")
        
        # 모드 설정
        self.piper.MotionCtrl_2(0x01, 0x01, 50, 0x00)
        time.sleep(0.1)
        
        # Joint Control로 홈 위치
        self.piper.JointCtrl(
            joint_1=0,
            joint_2=0,
            joint_3=0,
            joint_4=0,
            joint_5=0,
            joint_6=0
        )
        
        self.is_controlling = False
        self.is_initialized = False
        self.control_enabled = False
        
        time.sleep(2)
        print("HOME position reached.")
    
    def move_to_start(self):
        """시작 위치로 이동 (EndPose Control) - 그리퍼 방향 고정"""
        print("Moving to START position...")
        print(f"Target: X={self.start_position['X']}, Y={self.start_position['Y']}, Z={self.start_position['Z']}")
        print(f"Orientation: RX={self.fixed_orientation['RX']}, RY={self.fixed_orientation['RY']}, RZ={self.fixed_orientation['RZ']}")
        
        # EndPose 모드로 전환
        self.piper.MotionCtrl_2(0x01, 0x00, 100, 0x00)
        time.sleep(0.1)
        
        # 시작 위치로 이동 (마이크로미터 단위 직접 사용)
        self.piper.EndPoseCtrl(
            self.start_position['X'],
            self.start_position['Y'],
            self.start_position['Z'],
            self.fixed_orientation['RX'],
            self.fixed_orientation['RY'],
            self.fixed_orientation['RZ']
        )
        
        # 그리퍼 열기
        self.piper.GripperCtrl(self.gripper_open, 1000, 0x01, 0)
        
        self.current_robot_pos = self.start_position.copy()
        self.current_gripper = self.gripper_open
        self.is_controlling = False
        self.is_initialized = False
        self.control_enabled = False
        
        time.sleep(3)  # 이동 완료 대기 (충분한 시간)
        
        # 현재 위치 확인
        current_pose = self.piper.GetArmEndPoseMsgs()
        print(f"\nActual position reached:")
        print(f"  X: {current_pose.end_pose.X_axis}")
        print(f"  Y: {current_pose.end_pose.Y_axis}")
        print(f"  Z: {current_pose.end_pose.Z_axis}")
        print(f"  RX: {current_pose.end_pose.RX_axis}")
        print(f"  RY: {current_pose.end_pose.RY_axis}")
        print(f"  RZ: {current_pose.end_pose.RZ_axis}")
        
        print("\n✅ START position reached. Gripper pointing downward (fixed).")
        print("Press 'A' to activate hand tracking control.")
    
    def activate_control(self):
        """A 키를 눌러 제어 활성화"""
        if self.control_enabled:
            print("Control already active!")
            return
        
        print("\n🚀 Activating hand tracking control...")
        
        # 그리퍼 열기
        print("🖐️  Opening gripper...")
        self.piper.GripperCtrl(self.gripper_open, 1000, 0x01, 0)
        self.current_gripper = self.gripper_open
        time.sleep(0.5)
        
        print("Please show your hand to the camera to initialize reference position...")
        self.is_controlling = True
        self.is_initialized = False
        self.control_enabled = True
        
        # 버퍼 초기화
        self.position_buffer.clear()
        self.gripper_buffer.clear()
    
    def control_loop(self):
        """메인 제어 루프"""
        while self.running:
            if not self.is_controlling or not self.control_enabled:
                time.sleep(0.01)
                continue
            
            # 프레임 가져오기
            frames = self.pipeline.wait_for_frames()
            aligned_frames = self.align.process(frames)
            
            depth_frame = aligned_frames.get_depth_frame()
            color_frame = aligned_frames.get_color_frame()
            
            if not depth_frame or not color_frame:
                continue
            
            # NumPy 배열로 변환
            color_image = np.asanyarray(color_frame.get_data())
            
            # 손 감지
            hand_landmarks = self.get_hand_landmarks(color_image)
            
            if hand_landmarks:
                # 손목 위치 가져오기
                wrist_pixel, wrist_depth = self.get_wrist_position(
                    hand_landmarks, depth_frame, color_image)
                
                # 초기 위치 설정
                if not self.is_initialized:
                    if wrist_depth > 0:  # 유효한 depth 값
                        self.init_wrist_pixel = wrist_pixel
                        self.init_wrist_depth = wrist_depth
                        self.is_initialized = True
                        print(f"\n✅ Reference position initialized:")
                        print(f"   Pixel: {wrist_pixel}")
                        print(f"   Depth: {wrist_depth:.1f}mm")
                        print(f"\n🎮 Control active! Move your wrist to control the robot.")
                        
                        # 버퍼 초기화
                        self.position_buffer.clear()
                        self.gripper_buffer.clear()
                    continue
                
                # 제어 시작
                if wrist_depth > 0:
                    # 손목 이동량 계산 (픽셀 및 depth 변화)
                    dx_pixel = wrist_pixel[0] - self.init_wrist_pixel[0]  # 카메라 X (좌우)
                    dy_pixel = wrist_pixel[1] - self.init_wrist_pixel[1]  # 카메라 Y (위아래)
                    dz_depth = wrist_depth - self.init_wrist_depth          # 카메라 Z (앞뒤, mm 단위)
                    
                    # 좌표계 변환 (마이크로미터 단위)
                    # 카메라 X (좌우) → 로봇 Z (좌우)
                    # 카메라 Y (위아래) → 로봇 X (위아래)
                    # 카메라 Z (depth, 앞뒤) → 로봇 Y (앞뒤)
                    
                    delta_robot_x = int(-dy_pixel * self.pixel_to_um_y)  # 카메라 Y → 로봇 X (반전)
                    delta_robot_y = int(dz_depth * self.pixel_to_um_z)   # 카메라 Z(depth) → 로봇 Y
                    delta_robot_z = int(dx_pixel * self.pixel_to_um_x)   # 카메라 X → 로봇 Z
                    
                    # 새 위치 계산 (START 위치 기준)
                    new_position = {
                        'X': self.start_position['X'] - (delta_robot_y*2),
                        'Y': self.start_position['Y'] + (delta_robot_z*2),
                        'Z': self.start_position['Z'] + (delta_robot_x*2),
                        'RX': self.fixed_orientation['RX'],  # 고정
                        'RY': self.fixed_orientation['RY'],  # 고정
                        'RZ': self.fixed_orientation['RZ']   # 고정
                    }
                    
                    # 안전 구역 적용
                    new_position = self.apply_safety_zone(new_position)
                    
                    # 위치 스무딩
                    new_position = self.smooth_position(new_position)
                    
                    # 손가락 거리로 그리퍼 제어
                    finger_dist, thumb_pos, index_pos = self.get_finger_distance(
                        hand_landmarks, color_image)
                    gripper_value = self.map_finger_to_gripper(finger_dist)
                    gripper_value = self.smooth_gripper(gripper_value)
                    
                    # 로봇 제어 명령 전송
                    self.piper.MotionCtrl_2(0x01, 0x00, 100, 0x00)
                    self.piper.EndPoseCtrl(
                        new_position['X'],
                        new_position['Y'],
                        new_position['Z'],
                        new_position['RX'],
                        new_position['RY'],
                        new_position['RZ']
                    )
                    
                    # 그리퍼 제어 (절대값 제거, 음수 값도 처리 가능하도록)
                    self.piper.GripperCtrl(gripper_value, 1000, 0x01, 0)
                    
                    # 현재 위치 저장
                    self.current_robot_pos = new_position
                    self.current_gripper = gripper_value
            
            time.sleep(0.01)
    
    def visualize(self):
        """시각화 창"""
        while self.running:
            frames = self.pipeline.wait_for_frames()
            aligned_frames = self.align.process(frames)
            
            depth_frame = aligned_frames.get_depth_frame()
            color_frame = aligned_frames.get_color_frame()
            
            if not depth_frame or not color_frame:
                continue
            
            color_image = np.asanyarray(color_frame.get_data())
            depth_image = np.asanyarray(depth_frame.get_data())
            
            # Depth 시각화
            depth_colormap = cv2.applyColorMap(
                cv2.convertScaleAbs(depth_image, alpha=0.03), 
                cv2.COLORMAP_JET)
            
            # 손 감지 및 그리기
            hand_landmarks = self.get_hand_landmarks(color_image)
            
            if hand_landmarks:
                # 랜드마크 그리기
                self.mp_draw.draw_landmarks(
                    color_image, 
                    hand_landmarks, 
                    self.mp_hands.HAND_CONNECTIONS)
                
                # 손목 위치 표시
                wrist_pixel, wrist_depth = self.get_wrist_position(
                    hand_landmarks, depth_frame, color_image)
                cv2.circle(color_image, wrist_pixel, 10, (0, 255, 0), -1)
                cv2.putText(color_image, f"Depth: {wrist_depth:.1f}mm", 
                           (wrist_pixel[0] + 15, wrist_pixel[1]), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # 손가락 거리 표시
                finger_dist, thumb_pos, index_pos = self.get_finger_distance(
                    hand_landmarks, color_image)
                cv2.circle(color_image, thumb_pos, 8, (255, 0, 0), -1)
                cv2.circle(color_image, index_pos, 8, (255, 0, 0), -1)
                cv2.line(color_image, thumb_pos, index_pos, (255, 0, 0), 2)
                
                mid_x = (thumb_pos[0] + index_pos[0]) // 2
                mid_y = (thumb_pos[1] + index_pos[1]) // 2
                cv2.putText(color_image, f"Dist: {finger_dist:.1f}px", 
                           (mid_x, mid_y - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                
                # 초기 위치 표시
                if self.is_initialized and self.init_wrist_pixel:
                    cv2.circle(color_image, self.init_wrist_pixel, 8, (0, 0, 255), 2)
                    cv2.line(color_image, self.init_wrist_pixel, wrist_pixel, (0, 255, 255), 1)
            
            # 상태 정보 표시
            status_text = "IDLE"
            if not self.control_enabled:
                status_text = "IDLE - Press 'S' then 'A'"
            elif not self.is_initialized:
                status_text = "INITIALIZING - Show hand"
            else:
                status_text = "CONTROLLING"
                
            cv2.putText(color_image, f"Status: {status_text}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            # 로봇 위치 정보 (마이크로미터 → mm 변환하여 표시)
            if self.control_enabled and self.is_initialized:
                x_mm = self.current_robot_pos['X'] / 1000.0
                y_mm = self.current_robot_pos['Y'] / 1000.0
                z_mm = self.current_robot_pos['Z'] / 1000.0
                
                cv2.putText(color_image, 
                           f"Robot: X={x_mm:.1f}mm, Y={y_mm:.1f}mm, Z={z_mm:.1f}mm", 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                cv2.putText(color_image, f"Gripper: {self.current_gripper}", 
                           (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            
            # 조작 안내
            cv2.putText(color_image, "S:START | A:ACTIVATE | H:HOME | Q:QUIT", 
                       (10, color_image.shape[0] - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # 화면 표시
            images = np.hstack((color_image, depth_colormap))
            cv2.imshow('Piper Hand Control', images)
            
            # 키 입력 처리
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q') or key == ord('Q'):
                print("\n⚠️  Quitting and shutting down safely...")
                self.running = False
                break
            elif key == ord('s') or key == ord('S'):
                self.move_to_start()
            elif key == ord('a') or key == ord('A'):
                self.activate_control()
            elif key == ord('h') or key == ord('H'):
                self.move_to_home()
    
    def start(self):
        """시스템 시작"""
        print("="*60)
        print("Piper Hand Gesture Control System - Fixed Version")
        print("="*60)
        print("\n📍 START Position (micrometers):")
        print(f"   X: {self.start_position['X']} ({self.start_position['X']/1000:.1f}mm)")
        print(f"   Y: {self.start_position['Y']} ({self.start_position['Y']/1000:.1f}mm)")
        print(f"   Z: {self.start_position['Z']} ({self.start_position['Z']/1000:.1f}mm)")
        print(f"\n🔒 Fixed Orientation:")
        print(f"   RX: {self.fixed_orientation['RX']} ({self.fixed_orientation['RX']/1000:.1f}°)")
        print(f"   RY: {self.fixed_orientation['RY']} ({self.fixed_orientation['RY']/1000:.1f}°)")
        print(f"   RZ: {self.fixed_orientation['RZ']} ({self.fixed_orientation['RZ']/1000:.1f}°)")
        print("\n🎯 Coordinate Mapping:")
        print("   Camera X (left/right)  → Robot Z")
        print("   Camera Y (up/down)     → Robot X")
        print("   Camera Z (depth)       → Robot Y")
        print("\n⚙️  Control Parameters:")
        print(f"   1 pixel Camera X → {self.pixel_to_um_x}μm Robot Z")
        print(f"   1 pixel Camera Y → {self.pixel_to_um_y}μm Robot X")
        print(f"   1mm Camera depth → {self.pixel_to_um_z}μm Robot Y")
        print("\n🎮 Controls:")
        print("  S - Move to START position")
        print("  A - Activate hand tracking + Open gripper")
        print("  H - Return to HOME")
        print("  Q - Safe shutdown")
        print("\n✋ Hand Gestures:")
        print("  - Move wrist left/right  → Robot Z axis")
        print("  - Move wrist up/down     → Robot X axis")
        print("  - Move hand closer/away  → Robot Y axis")
        print("  - Pinch fingers          → Close gripper")
        print("  - Spread fingers         → Open gripper")
        print("="*60)
        
        self.running = True
        
        # Home 위치로 초기화
        self.move_to_home()
        
        # 제어 스레드 시작
        self.control_thread = threading.Thread(target=self.control_loop)
        self.control_thread.start()
        
        # 시각화 (메인 스레드)
        try:
            self.visualize()
        except KeyboardInterrupt:
            print("\n⚠️  Interrupted by user...")
        finally:
            self.cleanup()
    
    def safe_shutdown(self):
        """안전 종료 - 홈 위치로 이동 후 토크 해제"""
        if self.shutdown_in_progress:
            return
        
        self.shutdown_in_progress = True
        print("\n🛡️  Starting safe shutdown sequence...")
        
        try:
            # 제어 비활성화
            self.control_enabled = False
            self.is_controlling = False
            time.sleep(0.2)
            
            # 그리퍼 열기
            print("🖐️  Opening gripper...")
            self.piper.GripperCtrl(self.gripper_open, 1000, 0x01, 0)
            time.sleep(0.5)
            
            # 홈 포지션으로 이동
            print("🏠 Returning to HOME position...")
            self.piper.MotionCtrl_2(0x01, 0x01, 50, 0x00)
            time.sleep(0.3)
            
            self.piper.JointCtrl(
                joint_1=0,
                joint_2=0,
                joint_3=0,
                joint_4=0,
                joint_5=0,
                joint_6=0
            )
            print("⏳ Waiting for movement to complete... (3 seconds)")
            time.sleep(3.0)
            
            # 토크 해제
            print("🔓 Releasing torque...")
            self.piper.MotionCtrl_2(0x00, 0x01, 10, 0x00)
            time.sleep(0.5)
            
            print("✅ Safe shutdown complete! Robot can be moved manually.")
            
        except Exception as e:
            print(f"⚠️  Error during shutdown: {e}")
            try:
                self.piper.MotionCtrl_2(0x00, 0x01, 10, 0x00)
                time.sleep(0.3)
            except:
                pass
    
    def cleanup(self):
        """정리"""
        if self.shutdown_in_progress:
            return
        
        print("\n🔄 Stopping system...")
        self.running = False
        
        if self.control_thread:
            self.control_thread.join()
        
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
        
        print("✅ System stopped.")


if __name__ == "__main__":
    controller = PiperHandControl(can_port="can0")
    controller.start()