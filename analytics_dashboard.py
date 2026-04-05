import matplotlib.pyplot as plt
import io
import base64

def generate_analytics_plot(data_points):

    plt.figure(figsize=(6, 4))
    plt.bar(range(len(data_points)), data_points)
    plt.title("Weekly Delivery Efficiency")

    img = io.BytesIO()
    plt.savefig(img, format="png")
    plt.close()

    img.seek(0)
    return base64.b64encode(img.getvalue()).decode()
