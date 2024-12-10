import platform
from sqlalchemy import create_engine
import os
import tempfile
from dotenv import load_dotenv

load_dotenv()
CONNECT = os.getenv("CONNECT")
DATABASE_URL = os.getenv("DATABASE_URL")
pem_content = os.getenv("SSL_CA_CERT")

if CONNECT == "local":
    print("===Connect to LocalDB===")
    # ローカル環境でのデータベース接続設定
    engine = create_engine(os.getenv('DB'), echo=True)
else:
    print("===Connect to AzureDB===")
    # SSL証明書内容の確認と処理
    if pem_content is None:
        raise ValueError("SSL_CA_CERT is not set in environment variables.")

    pem_content = pem_content.replace("\\n", "\n").replace("\\", "")

    # 一時ファイル作成
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".pem") as temp_pem:
        temp_pem.write(pem_content)
        temp_pem_path = temp_pem.name

    with open(temp_pem_path, "r") as temp_pem:
        print("=====Temporary certificate file content:=====")
        print(temp_pem_path)
        azure(temp_pem.read())

    # データベース接続設定
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "ssl": {
                "ca": temp_pem_path
            }
        }
    )