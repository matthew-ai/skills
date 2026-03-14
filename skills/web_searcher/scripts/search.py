import sys
from ddgs import DDGS

def search(query, max_results=3):
    print(f"Searching for: {query} (max results: {max_results})...")
    results = DDGS().text(query, max_results=max_results)
    
    if not results:
        print("No results found.")
        return

    for i, r in enumerate(results):
        print(f"--- Result {i+1} ---")
        print(f"Title: {r['title']}")
        print(f"Link: {r['href']}")
        print(f"Snippet: {r['body']}\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        args = sys.argv[1:]
        max_results = 3
        query_parts = []
        i = 0
        while i < len(args):
            if args[i] == "--max-results" and i + 1 < len(args):
                try:
                    max_results = int(args[i+1])
                    i += 2
                except ValueError:
                    query_parts.append(args[i])
                    i += 1
            else:
                query_parts.append(args[i])
                i += 1
        
        query = " ".join(query_parts)
        if not query:
            print("Error: No search query provided.")
        else:
            search(query, max_results)
    else:
        print("Usage: python search.py <search query> [--max-results <number>]")
