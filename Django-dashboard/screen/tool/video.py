from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
import cv2

# 摄像头1
def video_feed(request):
    def generate_frames():
        cap = cv2.VideoCapture(0)  # 访问摄像头
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            _, jpeg = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
    return StreamingHttpResponse(generate_frames(), content_type='multipart/x-mixed-replace; boundary=frame')
