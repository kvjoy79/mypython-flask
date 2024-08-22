app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World2!'

if __name__ == '__main__':
    app.run(debug=True,port=8080)
