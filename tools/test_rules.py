from chromadb import PersistentClient

client = PersistentClient(path="chroma_db")
collection = client.get_collection("unity_ai_agent")

# 获取所有文档
results = collection.get()
print(f"Total documents: {len(results['ids'])}")
print("Sample document:")
print(results['documents'][2])
print("Sample metadata:")
print(results['metadatas'][2])
#print("Sample distances:")
#print(results['distances'][0])