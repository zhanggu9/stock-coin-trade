def search_knowledge(client, collection: str, vector, limit: int):
    result = client.query_points(
        collection_name=collection, query=vector, limit=limit, with_payload=True
    )
    return [{"score": point.score, "payload": point.payload}
            for point in result.points]
