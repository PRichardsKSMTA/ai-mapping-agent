import tiktoken

def count_tokens(text, model="gpt-4o"):
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

with open("your_file.csv", "r", encoding="utf-8") as file:
    content = file.read()
    print(f"Token count: {count_tokens(content)}")
