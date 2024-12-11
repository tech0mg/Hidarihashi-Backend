from flask import Flask, request, send_from_directory
from flask import jsonify
import json
from flask_cors import CORS
import os
import requests
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
from geopy.distance import geodesic
from db_control.connect import get_db_connection
from sqlalchemy.sql import text 


# Azure Database for MySQL
# REST APIでありCRUDを持っている
app = Flask(__name__, static_folder='static')
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 環境変数をロード
load_dotenv()

# API キー
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
NEXT_PUBLIC_GOOGLE_API_KEY = os.getenv("NEXT_PUBLIC_GOOGLE_API_KEY")


@app.route('/users', methods=['GET'])
def get_users():
    connection = get_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        return jsonify(users)
    except mysql.connector.Error as e:
        print(f"Error executing query: {e}")
        return jsonify({"error": "Failed to fetch data"}), 500
    finally:
        cursor.close()
        connection.close()


@app.route('/add_user', methods=['POST'])
def add_user():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    connection = get_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    cursor = connection.cursor()
    cursor.execute("INSERT INTO users (name, email) VALUES (%s, %s)", (name, email))
    connection.commit()
    cursor.close()
    connection.close()
    return jsonify({"message": "User added successfully!"})


@app.route("/")
def index():
    return "<p>Flask top page!</p>"


@app.route('/api/images', methods=['GET'])
def get_images():
    # データベース接続の取得
    try:
        connection = get_db_connection()
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return jsonify({"error": "Database connection failed"}), 500

    try:
        # SQLAlchemy の text を使用したクエリ
        query = text("SELECT event_name, image_path FROM event_data_child")
        results = connection.execute(query).mappings().all()

        # 辞書形式のデータをリストに変換
        images = [{"event_name": row["event_name"], "image_url": row["image_path"]} for row in results]
        
        # レスポンスを JSON 形式で作成
        response = jsonify({"images": images})
        response.headers["Content-Type"] = "application/json; charset=utf-8"
        return response, 200

    except Exception as e:
        print(f"Database query error: {e}")
        return jsonify({"error": "Failed to fetch images"}), 500

    finally:
        # SQLAlchemy の Connection オブジェクトを閉じる
        if 'connection' in locals():
            connection.close()


# しおりのイラスト一覧を取得するエンドポイント
@app.route('/api/illustrations', methods=['GET'])
def get_illustrations():
    illustrations_dir = os.path.join(app.static_folder, "illustrations")  # イラスト用のディレクトリ
    if not os.path.exists(illustrations_dir):
        return jsonify({"illustrations": []})  # ディレクトリが存在しない場合は空リストを返す

    illustration_files = os.listdir(illustrations_dir)
    illustrations = [
        {"name": os.path.splitext(file)[0], "url": f"/static/illustrations/{file}"}
        for file in illustration_files
    ]
    return jsonify({"illustrations": illustrations})

# リスト画像ファイルを提供するエンドポイント
@app.route('/static/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(os.path.join(app.static_folder, "images"), filename)


# しおりのイラストファイルを提供するエンドポイント
@app.route('/static/illustrations/<path:filename>')
def serve_illustration(filename):
    return send_from_directory(os.path.join(app.static_folder, "illustrations"), filename)

# しおりの天気を取得するために郵便番号を取得するエンドポイント
@app.route('/api/postal-code', methods=['GET'])
def get_postal_code():
    address = request.args.get('address')

    if not address:
        return jsonify({"error": "住所が指定されていません"}), 400

    try:
        response = requests.get(
            f"https://api.excelapi.org/post/zipcode", params={"address": address}
        )
        print("ExcelAPI Response:", response.text)  # デバッグログ

        if response.status_code == 200:
            postal_code = response.text.strip()
            return jsonify({"postalCode": postal_code}), 200
        else:
            return jsonify({"error": "郵便番号が見つかりませんでした"}), 404
    except Exception as e:
        print(f"Error fetching postal code: {e}")
        return jsonify({"error": "郵便番号取得中にエラーが発生しました"}), 500


# 天気情報をOpenWeatherMapから取得してくる


if not OPENWEATHERMAP_API_KEY:
    raise ValueError("OPENWEATHERMAP_API_KEY が環境変数に設定されていません。")

# 天気情報を取得するエンドポイント
@app.route('/api/weather', methods=['GET'])
def get_weather():
    postal_code = request.args.get('postalCode')
    country_code = request.args.get('countryCode', 'JP')  # デフォルトは日本の国コード

    if not postal_code:
        return jsonify({"error": "郵便番号が指定されていません"}), 400

    # 郵便番号にハイフンを挿入する処理
    if len(postal_code) == 7:  # 日本の郵便番号が7桁の場合
        postal_code = f"{postal_code[:3]}-{postal_code[3:]}"  # 例: 1234567 -> 123-4567

    try:
        print(f"Requesting OpenWeatherMap API with postalCode: {postal_code}, countryCode: {country_code}")
        # OpenWeatherMap API にリクエストを送信
        response = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "zip": f"{postal_code},{country_code}",
                "appid": OPENWEATHERMAP_API_KEY,
                "units": "metric",  # 摂氏で取得
                "lang": "ja"  # 日本語で取得
            }
        )
        if response.status_code == 200:
            weather_data = response.json()
            return jsonify(weather_data), 200
        else:
            print(f"Error response from OpenWeatherMap: {response.status_code}, {response.text}")
            return jsonify({"error": "天気情報が取得できませんでした"}), response.status_code
    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return jsonify({"error": "天気情報取得中にエラーが発生しました"}), 500


# 住所から緯度と経度を取得する
def get_lat_lng(address):
    print(f"Geocoding address: {address}")  # デバッグログ
    response = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": address, "key": NEXT_PUBLIC_GOOGLE_API_KEY}
    )
    print(f"Geocoding API Response: {response.text}")  # デバッグログ

    if response.status_code == 200:
        data = response.json()
        if "results" in data and len(data["results"]) > 0:
            location = data["results"][0]["geometry"]["location"]
            return {"lat": location["lat"], "lng": location["lng"]}
        else:
            print("Geocoding API error: No results found")
            return {"error": "指定された住所から緯度経度が取得できませんでした"}
    else:
        print(f"Geocoding API error: {response.status_code}, {response.text}")
        return {"error": f"Geocoding APIエラー: {response.status_code}"}

# 出発地と目的地の緯度・経度を使って中間地点を計算
def interpolate_path(start_coords, destination_coords):
    distance = geodesic(
        (start_coords['lat'], start_coords['lng']),
        (destination_coords['lat'], destination_coords['lng'])
    ).kilometers
    num_points = max(10, int(distance * 10))  # 1kmあたり10ポイントを追加
    lat_diff = destination_coords['lat'] - start_coords['lat']
    lng_diff = destination_coords['lng'] - start_coords['lng']
    return [
        {
            "lat": start_coords['lat'] + i * lat_diff / num_points,
            "lng": start_coords['lng'] + i * lng_diff / num_points
        }
        for i in range(num_points + 1)
    ]


# 経路の取得と表示
@app.route('/api/route', methods=['GET'])
def get_route():
    print("get_route called")
    start = request.args.get('start')
    destination = request.args.get('destination')
    print(f"Start: {start}, Destination: {destination}")

    if not start or not destination:
        return jsonify({"error": "出発地と目的地を指定してください"}), 400

    try:
        # 住所を緯度・経度に変換
        start_coords = get_lat_lng(start)
        destination_coords = get_lat_lng(destination)
        #print(f"Start Coords: {start_coords}, Destination Coords: {destination_coords}")

        if not start_coords or not destination_coords:
            print("Error: Failed to get coordinates")
            return jsonify({"error": "住所から緯度経度を取得できませんでした"}), 400
        
        # Google Maps Directions API を使用して最短経路を取得
        directions_url = "https://maps.googleapis.com/maps/api/directions/json"
        response = requests.get(
            directions_url,
            params={
                "origin": f"{start_coords['lat']},{start_coords['lng']}",
                "destination": f"{destination_coords['lat']},{destination_coords['lng']}",
                "mode": "driving",
                "key": NEXT_PUBLIC_GOOGLE_API_KEY
            }
        )

        if response.status_code != 200:
            return jsonify({"error": f"Directions API error: {response.status_code}"}), response.status_code

        directions_data = response.json()

        if "routes" not in directions_data or len(directions_data["routes"]) == 0:
            return jsonify({"error": "最短経路が見つかりませんでした"}), 500

        # 最短経路のポイントを取得
        route = directions_data["routes"][0]["overview_polyline"]["points"]

        # Google MapsのURLを生成
        google_maps_url = (
            f"https://www.google.com/maps/dir/?api=1&origin={start_coords['lat']},{start_coords['lng']}"
            f"&destination={destination_coords['lat']},{destination_coords['lng']}&travelmode=driving"
        )
        print(f"Generated Google Maps URL: {google_maps_url}")

        return jsonify({
            "polyline": route,
            "googleMapsUrl": google_maps_url
        }), 200

    except Exception as e:
        print(f"Error fetching route: {e}")
        return jsonify({"error": "経路情報取得中にエラーが発生しました"}), 500


# 写真アップロードのエンドポイントを追加
@app.route('/api/upload-photo', methods=['POST'])
def upload_photo():
    if 'photo' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['photo']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # 保存先ディレクトリの作成
    photos_dir = os.path.join(app.static_folder, "photos")
    if not os.path.exists(photos_dir):
        os.makedirs(photos_dir)

    # ファイルを保存
    file_path = os.path.join(photos_dir, file.filename)
    file.save(file_path)

    return jsonify({"message": "File uploaded successfully", "file_path": file_path}), 201


# アップロードされた写真一覧を取得するエンドポイント
@app.route('/api/photos', methods=['GET'])
def get_photos():
    photos_dir = os.path.join(app.static_folder, "photos")
    if not os.path.exists(photos_dir):
        return jsonify({"photos": []})  # ディレクトリが存在しない場合は空リストを返す

    photo_files = os.listdir(photos_dir)
    photo_urls = [f"/static/photos/{file}" for file in photo_files]
    return jsonify({"photos": photo_urls})



if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000, debug=True)
