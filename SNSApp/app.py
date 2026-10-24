#アプリのメインファイル

# おためし表示
from flask import Flask, send_from_directory

app = Flask(__name__)

@app.route("/", methods=["GET"])
def hello():
    return send_from_directory("templates", "base.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
