import socket
import struct
import time
import sys
import serial # pyserial 라이브러리 임포트

# 기본 통신 설정 (소켓용)
DEFAULT_TCP_IP = '192.168.0.11'
DEFAULT_TCP_PORT = 5000

# AQM-200(LG) 센서의 Modbus 슬레이브 ID (주소)
SLAVE_ID = 1 # AQM-200(LG) 센서는 S12 딥스위치로 Modbus ID를 설정할 수 있습니다. [cite: 113, 114, 142]

# 센서 데이터 Hold Register 주소 (메뉴얼 p.10 참조)
# CO2: 0x0050 (십진수 80) [cite: 154]
# CO: 0x0051 (십진수 81) [cite: 154]
# TVOC: 0x0052 (십진수 82) [cite: 154]
# Temperature: 0x0053 (십진수 83) [cite: 154]
# Humidity: 0x0054 (십진수 84) [cite: 154]

REG_ADDR_CO2 = 0x0050  # CO2 레지스터 주소 (십진수 80) [cite: 154]
NUM_REGISTERS = 5      # 읽어올 레지스터 개수 (CO2부터 습도까지 5개) [cite: 153]

# Modbus RTU 통신 설정
BAUDRATE = 9600  # AQM-200(LG) 매뉴얼에 명시된 Baud rate 
BYTESIZE = 8     # Data Bit 
PARITY = serial.PARITY_NONE # Parity Bit 
STOPBITS = 1     # Stop Bit 
TIMEOUT = 25      # Serial 통신 타임아웃 (초)

def calculate_crc16(data):
    """
    Modbus RTU CRC-16을 계산합니다.
    Args:
        data (bytes): CRC를 계산할 바이트 데이터
    Returns:
        int: 계산된 CRC-16 값
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc

def create_modbus_rtu_request(slave_id, function_code, start_address, num_registers):
    """
    Modbus RTU Read Holding Registers (FC 0x03) 요청 프레임을 생성합니다.
    Args:
        slave_id (int): 슬레이브 ID
        function_code (int): 기능 코드 (홀딩 레지스터 읽기는 0x03)
        start_address (int): 시작 레지스터 주소
        num_registers (int): 읽어올 레지스터 개수
    Returns:
        bytes: CRC가 포함된 Modbus RTU 요청 프레임
    """
    # 프레임 구조: 슬레이브 ID (1바이트), 기능 코드 (1바이트), 시작 주소 (2바이트), 레지스터 개수 (2바이트)
    # 시작 주소와 레지스터 개수는 빅 엔디안 (Big-endian)으로 변환
    request_pdu = struct.pack('>BBHH', slave_id, function_code, start_address, num_registers)
    
    # CRC 계산
    crc = calculate_crc16(request_pdu)
    
    # CRC를 리틀 엔디안 (Little-endian)으로 바이트 배열에 추가
    full_request = request_pdu + struct.pack('<H', crc)
    
    return full_request

def parse_modbus_rtu_response(response_bytes, expected_slave_id, expected_function_code, expected_num_bytes):
    """
    Modbus RTU Read Holding Registers (FC 0x03) 응답 프레임을 파싱합니다.
    Args:
        response_bytes (bytes): Modbus RTU 응답 바이트
        expected_slave_id (int): 예상되는 슬레이브 ID
        expected_function_code (int): 예상되는 기능 코드
        expected_num_bytes (int): 예상되는 데이터 바이트 수
    Returns:
        list: 파싱된 레지스터 값 리스트, 또는 None (오류 시)
    """
    if len(response_bytes) < 5: # 최소 길이: ID(1) + FC(1) + 바이트수(1) + CRC(2)
        print("응답 길이가 너무 짧습니다.")
        return None

    response_slave_id = response_bytes[0]
    response_function_code = response_bytes[1]
    data_byte_count = response_bytes[2]
    
    # CRC를 제외한 데이터 부분
    received_data_for_crc = response_bytes[:-2]
    received_crc = struct.unpack('<H', response_bytes[-2:])[0]
    calculated_crc = calculate_crc16(received_data_for_crc)

    if response_slave_id != expected_slave_id:
        print(f"슬레이브 ID 불일치: 예상 {expected_slave_id}, 수신 {response_slave_id}")
        return None
    
    if response_function_code != expected_function_code:
        print(f"기능 코드 불일치: 예상 {expected_function_code}, 수신 {response_function_code}")
        # 예외 응답 처리 (오류 코드 0x83 등) [cite: 144, 145]
        if response_function_code == (expected_function_code | 0x80):
            exception_code = response_bytes[2]
            print(f"Modbus 예외 응답: 오류 코드 {exception_code} [cite: 146]")
        return None

    if data_byte_count != expected_num_bytes:
        print(f"데이터 바이트 수 불일치: 예상 {expected_num_bytes}, 수신 {data_byte_count}")
        return None
        
    if received_crc != calculated_crc:
        print(f"CRC 불일치: 수신 {received_crc:04X}, 계산 {calculated_crc:04X}")
        return None

    # 레지스터 값 추출 (각 레지스터는 2바이트)
    registers = []
    # 데이터 시작 위치: ID(1) + FC(1) + 바이트수(1) = 3
    # 데이터 끝 위치: 총 길이 - CRC(2)
    for i in range(3, 3 + data_byte_count, 2):
        registers.append(struct.unpack('>H', response_bytes[i:i+2])[0]) # 빅 엔디안으로 레지스터 값 파싱 [cite: 154]

    return registers

def read_data_over_socket(ip, port):
    sock = None
    try:
        while True:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(25) # 5초 타임아웃 설정

            try:
                sock.connect((ip, port))
                print(f"TCP 클라이언트가 {ip}:{port}에 연결되었습니다.")

                modbus_request_bytes = create_modbus_rtu_request(SLAVE_ID, 0x03, REG_ADDR_CO2, NUM_REGISTERS)
                
                print(f"전송할 Hex 데이터: {modbus_request_bytes.hex().upper()}")

                sock.sendall(modbus_request_bytes)
                
                response = sock.recv(1024) 
                
                
                if response:
                    
                    print(response)
                    print(f"수신된 Hex 데이터: {response.hex().upper()}")

                    registers = parse_modbus_rtu_response(response, SLAVE_ID, 0x03, NUM_REGISTERS * 2)

                    if registers is not None:
                        co2_ppm = registers[0] # [cite: 154]
                        co_ppm = registers[1] # [cite: 154]
                        tvoc_ppb = registers[2] # [cite: 154]
                        temperature_c = registers[3] / 10.0 # 온도는 10을 나눈 값 [cite: 154]
                        humidity_percent = registers[4] # [cite: 154]

                        print(f"\n--- AQM-200(LG) 센서 데이터 (슬레이브 ID: {SLAVE_ID}) ---")
                        print(f"CO2: {co2_ppm} ppm")
                        print(f"CO: {co_ppm} ppm")
                        print(f"TVOC: {tvoc_ppb} ppb")
                        print(f"온도: {temperature_c}°C")
                        print(f"습도: {humidity_percent}%")
                    else:
                        print("응답 파싱에 실패했습니다.")
                else:
                    print("응답이 없습니다.")

            except socket.timeout:
                print("연결 타임아웃 또는 데이터 수신 타임아웃. 다시 시도합니다.")
            except ConnectionRefusedError:
                print(f"연결 거부: {ip}:{port}에 연결할 수 없습니다. 컨버터가 실행 중인지, IP 및 포트가 올바른지 확인하세요. 다시 시도합니다.")
            except Exception as e:
                print(f"소켓 통신 오류 발생: {e}. 다시 시도합니다.")
            finally:
                if sock:
                    sock.close()
                    print("TCP 클라이언트 연결이 종료되었습니다.")
            
            time.sleep(3) # 다음 요청까지 3초 대기
            print("-" * 50) 

    except KeyboardInterrupt:
        print("\nCtrl+C가 감지되었습니다. 프로그램을 종료합니다.")
    except Exception as e:
        print(f"소켓 통신 루프 중 예상치 못한 오류 발생: {e}")
    finally:
        if sock:
            sock.close()

def read_data_over_serial(port):
    ser = None
    try:
        while True:
            try:
                # 시리얼 포트 열기
                ser = serial.Serial(
                    port=port,
                    baudrate=BAUDRATE,
                    bytesize=BYTESIZE,
                    parity=PARITY,
                    stopbits=STOPBITS,
                    timeout=TIMEOUT
                )
                print(f"시리얼 포트 {port}에 연결되었습니다.")

                modbus_request_bytes = create_modbus_rtu_request(SLAVE_ID, 0x03, REG_ADDR_CO2, NUM_REGISTERS)
                
                print(f"전송할 Hex 데이터: {modbus_request_bytes.hex().upper()}")

                ser.write(modbus_request_bytes)
                
                # 응답 수신
                # Modbus RTU 응답의 최소 길이 (슬레이브ID + 기능코드 + 바이트수 + 데이터 + CRC)
                # 데이터가 5개 레지스터 (10바이트)이므로, 1 + 1 + 1 + 10 + 2 = 15바이트
                response = ser.read(15) # 예상되는 최대 응답 길이만큼 읽기

                if response:
                    print(f"수신된 Hex 데이터: {response.hex().upper()}")

                    registers = parse_modbus_rtu_response(response, SLAVE_ID, 0x03, NUM_REGISTERS * 2)

                    if registers is not None:
                        co2_ppm = registers[0]
                        co_ppm = registers[1] 
                        tvoc_ppb = registers[2]
                        temperature_c = registers[3] / 10.0 # 온도는 10을 나눈 값 [cite: 154]
                        humidity_percent = registers[4]

                        print(f"\n--- AQM-200(LG) 센서 데이터 (슬레이브 ID: {SLAVE_ID}) ---")
                        print(f"CO2: {co2_ppm} ppm")
                        print(f"CO: {co_ppm} ppm")
                        print(f"TVOC: {tvoc_ppb} ppb")
                        print(f"온도: {temperature_c}°C")
                        print(f"습도: {humidity_percent}%")
                    else:
                        print("응답 파싱에 실패했습니다.")
                else:
                    print("응답이 없습니다.")

            except serial.SerialException as e:
                print(f"시리얼 포트 오류: {e}. 포트를 다시 확인하거나 다른 포트를 시도하세요. 다시 시도합니다.")
            except Exception as e:
                print(f"시리얼 통신 오류 발생: {e}. 다시 시도합니다.")                
            
            time.sleep(3) # 다음 요청까지 3초 대기
            print("-" * 50)
            if ser and ser.is_open:
                ser.close()
                print("시리얼 포트 연결이 종료되었습니다.")            

    except KeyboardInterrupt:
        print("\nCtrl+C가 감지되었습니다. 프로그램을 종료합니다.")
    except Exception as e:
        print(f"시리얼 통신 루프 중 예상치 못한 오류 발생: {e}")
    finally:
        if ser and ser.is_open:
            ser.close()

if __name__ == "__main__":
    print("--- AQM-200(LG) 센서 데이터 로거 ---")
    while True:
        print("\n통신 방법을 선택하세요:")
        print("1. Serial (RS-485 to USB 컨버터 사용)")
        print("2. Socket (TCP/IP, 예: 이더넷 컨버터 사용)")
        
        choice = input("선택 (1 또는 2): ")

        if choice == '1':
            if sys.platform.startswith('win'):
                port = input("시리얼 포트 (예: COM1, COM2): ").strip().upper()
            else: # Linux, macOS
                port = input("시리얼 포트 (예: /dev/ttyUSB0, /dev/ttyS0): ").strip()
            print(f"시리얼 통신으로 데이터를 읽습니다. 포트: {port}")
            read_data_over_serial(port)
            break # 통신 루프가 종료되면 메인 루프도 종료
        elif choice == '2':
            ip_input = input(f"컨버터 IP 주소 (기본값: {DEFAULT_TCP_IP}): ").strip()
            ip = ip_input if ip_input else DEFAULT_TCP_IP
            
            port_input = input(f"컨버터 포트 번호 (기본값: {DEFAULT_TCP_PORT}): ").strip()
            try:
                port = int(port_input) if port_input else DEFAULT_TCP_PORT
            except ValueError:
                print("유효하지 않은 포트 번호입니다. 기본값으로 설정됩니다.")
                port = DEFAULT_TCP_PORT

            print(f"소켓 통신으로 데이터를 읽습니다. IP: {ip}, 포트: {port}")
            read_data_over_socket(ip, port)
            break # 통신 루프가 종료되면 메인 루프도 종료
        else:
            print("잘못된 선택입니다. 1 또는 2를 입력해주세요.")
            time.sleep(1) # 다시 선택하기 전 잠시 대기