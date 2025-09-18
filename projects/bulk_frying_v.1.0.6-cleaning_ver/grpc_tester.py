import sys
import os
import time
import json

# gRPC 라이브러리 직접 import
import grpc
# protobuf로 생성된 파일들을 찾을 수 있도록 경로 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "pkg/app/grpcjs"))
sys.path.append(os.path.join(current_dir, "pkg/app/grpcjs/grpc_gen"))

# 최신 protobuf 파일 임포트
import template_pb2
import template_pb2_grpc

def process_recipe_v2(data):
    """
    JSON 데이터에서 'command'가 1이고 'input_type'이 1인 레시피 항목의
    'basket_index' 값을 추출하여 'trunk' 리스트에 저장하고, 결과를 출력하는 함수입니다.
    'trunk' 리스트는 3f, 2f, 1f로 나뉘며, 각 인덱스에 값이 존재하는지 여부를 1 또는 0으로 표시합니다.

    Args:
        data (dict): 파이썬 딕셔너리 형식의 데이터.
    
    Returns:
        dict: 처리된 trunk 리스트를 포함하는 딕셔너리.
    """
    # trunk 리스트를 0으로 초기화합니다.
    # 각 인덱스는 [0] 1, [1] 2, [2] 3 을 의미합니다.
    trunk_3f = [0, 0, 0]
    # 각 인덱스는 [0] 4, [1] 5, [2] 6 을 의미합니다.
    trunk_2f = [0, 0, 0]
    # 각 인덱스는 [0] 7, [1] 8, [2] 9 을 의미합니다.
    trunk_1f = [0, 0, 0]

    # 'Recipe' 키가 존재하는지 확인합니다.
    if "Recipe" not in data:
        print("Error: 'Recipe' 키가 JSON 데이터에 없습니다.")
        return {
            "trunk_3f": trunk_3f,
            "trunk_2f": trunk_2f,
            "trunk_1f": trunk_1f
        }

    # 'Recipe' 리스트를 순회합니다.
    for item in data["Recipe"]:
        # 'command'가 1이고 'input_type'이 1인지 확인합니다.
        if item.get("command") == 1 and item.get("input_type") == 1:
            basket_index = item.get("basket_index")
            
            # 'basket_index' 값이 유효한지 확인하고, 해당 trunk 리스트의 값을 1로 변경합니다.
            if basket_index is not None:
                if 1 <= basket_index <= 3:
                    # 1~3번은 trunk_3f에 해당합니다.
                    trunk_3f[basket_index - 1] = 1
                elif 4 <= basket_index <= 6:
                    # 4~6번은 trunk_2f에 해당합니다.
                    trunk_2f[basket_index - 4] = 1
                elif 7 <= basket_index <= 9:
                    # 7~9번은 trunk_1f에 해당합니다.
                    trunk_1f[basket_index - 7] = 1
    
    return {
        "trunk_3f": trunk_3f,
        "trunk_2f": trunk_2f,
        "trunk_1f": trunk_1f
    }

def run_dummy_client(ip, port):
    """
    gRPC 더미 클라이언트를 실행합니다.
    키보드 입력을 통해 데이터를 서버에 전달합니다.
    """
    channel = None
    try:
        # gRPC 채널 생성
        channel = grpc.insecure_channel(f"{ip}:{port}")
        stub = template_pb2_grpc.GRPCGlobalVariableTaskStub(channel)
        
        print(f"gRPC 더미 클라이언트가 {ip}:{port}에 연결되었습니다.")
        print("Ctrl+C를 누르면 종료됩니다.")
        
        while True:
            # 사용자로부터 명령 입력 받기
            print("명령어는 '1:set_int', '2:get_int', '3:set_ints', '4:get_ints', '5:set_string_with_id', '6:get_string_with_id', '7:send_recipe_json', '8:set_float', '9:get_float'가 있습니다.")
            command = input("명령을 입력하세요: ").lower().strip()
            
            if command == '1': # set_int
                try:
                    user_input = input("인덱스(정수), 값(정수)을 콤마(,)로 구분해서 입력하세요 (예: 1,100): ")
                    idx, val = map(int, user_input.split(','))
                    request = template_pb2.GInt(idx=idx, val=val)
                    stub.SetInt(request)
                    print(f"서버에 인덱스 {idx}, 값 {val} 전달 완료.")
                except (ValueError, grpc.RpcError) as e:
                    print(f"오류 발생: {e}")
            
            elif command == '2': # get_int
                try:
                    idx = int(input("인덱스(정수)를 입력하세요: "))
                    request = template_pb2.IntVal(val=idx)
                    response = stub.GetInt(request)
                    print(f"서버로부터 받은 값: {response.val}")
                except (ValueError, grpc.RpcError) as e:
                    print(f"오류 발생: {e}")

            elif command == '3': # set_ints
                try:
                    user_input = input("시작 인덱스(정수)와 값들(콤마로 구분)을 콤마(,)로 구분해서 입력하세요 (예: 1,10,20,30): ")
                    parts = user_input.split(',')
                    idx = int(parts[0].strip())
                    vals = [int(x.strip()) for x in parts[1:]]
                    request = template_pb2.GInts(idx=idx, val=vals)
                    stub.SetInts(request)
                    print(f"서버에 인덱스 {idx}부터 값 {vals} 전달 완료.")
                except (ValueError, grpc.RpcError) as e:
                    print(f"오류 발생: {e}")

            elif command == '4': # get_ints
                try:
                    user_input = input("시작 인덱스(정수)와 가져올 개수(정수)를 콤마(,)로 구분해서 입력하세요 (예: 1,5): ")
                    idx, count = map(int, user_input.split(','))
                    request = template_pb2.GInt(idx=idx, val=count)
                    response = stub.GetInts(request)
                    print(f"서버로부터 받은 값들: {list(response.val)}")
                except (ValueError, grpc.RpcError) as e:
                    print(f"오류 발생: {e}")

            # ID와 함께 문자열을 주고받는 기능
            elif command == '5': # set_string_with_id
                try:
                    user_input = input("ID(정수)와 문자열 값을 콤마(,)로 구분해서 입력하세요 (예: 1,test_string): ")
                    parts = user_input.split(',')
                    id = int(parts[0].strip())
                    val = ','.join(parts[1:]).strip() # 콤마를 포함한 문자열을 처리
                    request = template_pb2.StringWithId(id=id, val=val)
                    stub.SetStringWithId(request)
                    print(f"서버에 ID {id}, 문자열 '{val}' 전달 완료.")
                except (ValueError, grpc.RpcError) as e:
                    print(f"오류 발생: {e}")

            elif command == '6': # get_string_with_id
                try:
                    id = int(input("ID(정수)를 입력하세요: "))
                    request = template_pb2.StringId(id=id)
                    response = stub.GetStringWithId(request)
                    
                    # 수신된 문자열을 JSON으로 변환하여 출력
                    try:
                        print(f"서버로부터 받은 문자열 (ID {response.id}): {response.val}")
                        json_data = json.loads(response.val)
                        result = process_recipe_v2(json_data)
                        print("trunk_3f:", result["trunk_3f"])
                        print("trunk_2f:", result["trunk_2f"])
                        print("trunk_1f:", result["trunk_1f"])
                    except json.JSONDecodeError:
                        print(f"서버로부터 받은 문자열 (ID {response.id}): '{response.val}'")
                    
                except (ValueError, grpc.RpcError) as e:
                    print(f"오류 발생: {e}")

            # 7번 명령어를 입력하면 레시피 JSON을 자동으로 전송
            elif command == '7':
                try:
                    # recipe_examp.json 파일에서 JSON 데이터 읽기
                    json_file_path = os.path.join(current_dir, "recipe_examp.json")
                    with open(json_file_path, 'r', encoding='utf-8') as f:
                        recipe_json = f.read()

                    # ID 191로 레시피 JSON 문자열을 보냅니다.
                    request = template_pb2.StringWithId(id=191, val=recipe_json)
                    stub.SetStringWithId(request)
                    print(f"서버에 ID 191, 레시피 JSON 데이터 전달 완료.")
                except FileNotFoundError:
                    print(f"오류: '{json_file_path}' 파일을 찾을 수 없습니다. 파일 경로를 확인해주세요.")
                except Exception as e:
                    print(f"예상치 못한 오류 발생: {e}")

            elif command == '8': # set_float
                try:
                    user_input = input("인덱스(정수), 값(실수)을 콤마(,)로 구분해서 입력하세요 (예: 100,3.14): ")
                    parts = user_input.split(',')
                    idx = int(parts[0].strip())
                    float_val = float(parts[1].strip())

                    request = template_pb2.GFloat(idx=idx, val=float_val)
                    stub.SetFloat(request)
                    print(f"서버에 인덱스 {idx}에 float 값 {float_val} 전달 완료.")

                except (ValueError, IndexError, grpc.RpcError) as e:
                    print(f"오류 발생: {e}")
            
            elif command == '9': # get_float
                try:
                    idx = int(input("인덱스(정수)를 입력하세요: "))
                    request = template_pb2.IntVal(val=idx)
                    response = stub.GetFloat(request)
                    print(f"서버로부터 받은 float 값: {response.val}")
                except (ValueError, grpc.RpcError) as e:
                    print(f"오류 발생: {e}")

            else:
                print("알 수 없는 명령입니다.")
            
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nCtrl+C가 감지되었습니다. 클라이언트를 종료합니다.")
    except Exception as e:
        print(f"예상치 못한 오류 발생: {e}")
    finally:
        if channel:
            channel.close()
            print("클라이언트 연결 종료.")
        sys.exit(0)

if __name__ == '__main__':
    # 서버 IP와 포트를 여기에 설정하세요.
    SERVER_IP = "192.168.5.115" 
    SERVER_PORT = 503
    run_dummy_client(SERVER_IP, SERVER_PORT)
