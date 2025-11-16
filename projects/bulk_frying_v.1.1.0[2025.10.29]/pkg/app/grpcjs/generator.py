import os
import sys
import glob

# 스크립트가 위치한 디렉토리를 기준으로 경로를 설정합니다.
script_directory = os.path.dirname(os.path.abspath(__file__))
print(f"스크립트 디렉토리: {script_directory}")

# proto 파일이 있는 디렉토리 경로
proto_dir_name = "proto"
proto_file_directory = os.path.join(script_directory, proto_dir_name)
print(f"Proto 파일 디렉토리: {proto_file_directory}")

# 결과물이 저장될 디렉토리 경로
output_path = os.path.join(script_directory, "grpc_gen")
print(f"결과물 디렉토리: {output_path}")

# 결과물 디렉토리와 __init__.py 파일이 없으면 생성합니다.
if not os.path.exists(output_path):
    os.makedirs(output_path)
if not os.path.exists(os.path.join(output_path, "__init__.py")):
    with open(os.path.join(output_path, "__init__.py"), "w") as f:
        pass

# proto 디렉토리가 있는지 확인합니다.
if not os.path.isdir(proto_file_directory):
    print(f"오류: Proto 디렉토리를 찾을 수 없습니다. 경로: '{proto_file_directory}'")
    sys.exit(1)

# proto 디렉토리 안의 모든 .proto 파일을 찾습니다.
proto_files = glob.glob(os.path.join(proto_file_directory, "*.proto"))

if not proto_files:
    print(f"오류: Proto 디렉토리에서 .proto 파일을 찾을 수 없습니다. 경로: '{proto_file_directory}'")
    sys.exit(1)

# 찾은 각 .proto 파일에 대해 gRPC 코드를 생성합니다.
for proto_file_path in proto_files:
    proto_file_name = os.path.basename(proto_file_path)
    print(f"\n컴파일 중: {proto_file_name}...")
    
    command = (
        f"python -m grpc_tools.protoc "
        f"--proto_path={proto_file_directory} "
        f"--python_out={output_path} "
        f"--grpc_python_out={output_path} "
        f"{proto_file_path}"
    )
    
    print(f"실행 명령어: {command}")
    os.system(command)

print("\ngRPC 코드 생성이 완료되었습니다.")


'''
import os

current_directory = os.getcwd()
print(current_directory)

# Path of proto file
build_protobuf_file = "EtherCATCommgRPCServer.proto"
proto_file_directory = current_directory + "\\grpcjs\\proto"
proto_file_path = current_directory + "\\grpcjs\\proto\\" + build_protobuf_file
output_path = current_directory + "\\grpcjs\\grpc_gen"

# Create output directory if it doesn't exist
if not os.path.exists(output_path):
    os.makedirs(output_path)

# Generate gRPC code command
print("asdfa")
os.system(f"python -m grpc_tools.protoc --proto_path={proto_file_directory} --python_out={output_path} --grpc_python_out={output_path} {proto_file_path}")
print("asdfa")
'''