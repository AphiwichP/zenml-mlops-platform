from zenml import pipeline, step

@step
def ingest() -> str:
    return "hello from ZenML lab"

@step
def process(data: str) -> str:
    result = data.upper()
    print(f"Processed: {result}")
    return result

@pipeline
def smoke_pipeline():
    data = ingest()
    process(data)

if __name__ == "__main__":
    smoke_pipeline()
