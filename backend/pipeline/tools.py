from duckduckgo_search import DDGS

def web_search(query: str, max_results: int = 3) -> str:
    """
    DuckDuckGo 검색을 사용하여 사용자의 query에 대한 최신 정보를 웹에서 검색합니다.
    결과를 문자열(String) 형태로 반환합니다.
    """
    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return "No internet results found for the query."
        
        # Format results into a readable string
        formatted_results = []
        for index, res in enumerate(results):
            title = res.get('title', 'No Title')
            body = res.get('body', 'No Content')
            href = res.get('href', 'No URL')
            formatted_results.append(f"[{index + 1}] Title: {title}\nURL: {href}\nSnippet: {body}")
            
        return "\n\n".join(formatted_results)
    except Exception as e:
        return f"Web search failed with error: {str(e)}"
