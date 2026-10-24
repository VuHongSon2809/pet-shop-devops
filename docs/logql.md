# Truy vấn log bằng LogQL (Grafana → Explore → datasource **Loki**)

Promtail gắn nhãn `job` theo tên service trong Docker Compose: `nginx`, `web`, `db`, `grafana`...
Chọn khoảng thời gian **Last 15 minutes**, truy cập website vài lần để sinh log, rồi bấm **Run query**.

## Truy vấn cơ bản (yêu cầu của đề)

| # | Truy vấn | Ý nghĩa |
|---|---|---|
| A | `{job="nginx"}` | Toàn bộ log truy cập của Nginx (mỗi dòng là một JSON) |
| B | `{job="nginx"} \| json \| method="GET"` | Tách trường JSON rồi chỉ giữ request GET |
| C | `sum(count_over_time({job="nginx"}[5m]))` | Đếm số dòng log Nginx trong cửa sổ 5 phút (dạng biểu đồ) |

## Truy vấn mở rộng

| # | Truy vấn | Ý nghĩa |
|---|---|---|
| D | `{job="nginx"} \| json \| status >= 400` | Chỉ các request lỗi (404, 429, 5xx) |
| E | `sum by (status) (count_over_time({job="nginx"} \| json [5m]))` | Số request theo mã HTTP |
| F | `topk(5, sum by (path) (count_over_time({job="nginx"} \| json [15m])))` | 5 đường dẫn được truy cập nhiều nhất |
| G | `{job="web"} \| logfmt \| event=~"appointment_.*"` | Sự kiện nghiệp vụ: tạo/sửa/đổi trạng thái lịch hẹn |
| H | `{job="web"} \| logfmt \| event="login_failed"` | Đăng nhập thất bại (phát hiện dò mật khẩu) |
| I | `{job="web"} != "/healthz"` | Log của web, bỏ các dòng healthcheck định kỳ |
| J | `{job="nginx"} \| json \| status = 429` | Request bị Nginx chặn do vượt giới hạn đăng nhập |

## Giải thích cú pháp

- `{job="nginx"}` – **stream selector**: chọn luồng log theo nhãn.
- `|= "chuỗi"` / `!= "chuỗi"` – **line filter**: giữ/bỏ dòng có chứa chuỗi.
- `| json`, `| logfmt` – **parser**: tách nội dung dòng log thành các trường (method, status, event...).
- `| status >= 400` – **label filter** trên trường vừa tách.
- `count_over_time(...[5m])` – đếm số dòng log trong cửa sổ 5 phút tại mỗi thời điểm; `sum by (x)` cộng theo nhóm.

> Prometheus dùng **PromQL** cho metrics (số đo theo thời gian), còn Loki dùng **LogQL** cho log (dòng văn bản).
