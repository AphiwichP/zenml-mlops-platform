import random
from zenml import pipeline, step
from zenml.logger import get_logger

logger = get_logger(__name__)

# Step 1: สร้าง dataset จำลอง
@step
def ingest_data() -> list[float]:
    # fixed dataset — ZenML จะ cache step นี้ถ้า code ไม่เปลี่ยน
    data = [12.5, 88.3, 45.1, 67.2, 23.8, 91.0, 34.6, 55.5,
            78.9, 10.2, 60.4, 42.7, 95.1, 30.0, 71.3, 18.6,
            83.4, 50.0, 25.9, 66.7]
    logger.info(f"Ingested {len(data)} records")
    return data

# Step 2: Normalize ข้อมูล (0-1)
@step
def preprocess(data: list[float]) -> list[float]:
    min_val = min(data)
    max_val = max(data)
    normalized = [(x - min_val) / (max_val - min_val) for x in data]
    logger.info(f"Normalized: min={min_val}, max={max_val}")
    return normalized

# Step 3: "Train model" — คำนวณ mean เป็น threshold
@step
def train(data: list[float]) -> float:
    threshold = sum(data) / len(data)
    logger.info(f"Model threshold: {threshold:.4f}")
    return threshold

# Step 4: Evaluate — นับว่ากี่ % อยู่เหนือ threshold
@step
def evaluate(data: list[float], threshold: float) -> dict:
    above = sum(1 for x in data if x > threshold)
    accuracy = above / len(data)
    metrics = {
        "threshold": round(threshold, 4),
        "samples_above": above,
        "accuracy": round(accuracy, 4),
    }
    logger.info(f"Metrics: {metrics}")
    return metrics

@pipeline
def ml_pipeline():
    raw = ingest_data()
    processed = preprocess(raw)
    model = train(processed)
    evaluate(processed, model)

if __name__ == "__main__":
    ml_pipeline()
