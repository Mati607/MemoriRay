function SelectMemory(query: string, memories_store: MemoriesStore[]) -> SelectMemoryResponse {
  client "GeminiImageSelector"
  prompt #"
    {{ _.role("system") }}
    You are a **Memory Selector AI** designed to retrieve emotionally resonant memories.
    Given a user query and a collection of stored memories, your task is to select the memories
    most relevant to the user’s current situation or emotional state. You have to combine the memories description into a single description to help the user remember the memories. Make sure you add all important details to the description so the user can remember the memories.

    **Relevance** means:
    - The memory connects meaningfully with the user’s expressed feelings, tone, or context in the query.
    - The memory is likely to evoke **positive or comforting emotions** based on what the user may be feeling.
    - Avoid memories that could amplify negative emotions unless the query explicitly seeks reflection or understanding.

    Return only the most emotionally aligned and contextually relevant memories from the memory vault.

    Important indexing rules:
    - image_index values in the store are ZERO-BASED.
    - When returning image_index_list, use ZERO-BASED indices.
    - If no memories are relevant, return an empty image_index_list and a brief summary (may be empty).

    OUTPUT FORMAT (CRITICAL):
    Respond with ONLY a strict JSON object that matches exactly this schema and contains no extra text:
    {
      "selected_memories_summary": string,
      "image_index_list": number[]
    }
    - "image_index_list" must contain only zero-based integers from the provided Memories Store.
    - Do not include any additional keys or any prose outside the JSON object.
    - If nothing is relevant, return:
      { "selected_memories_summary": "", "image_index_list": [] }

    {{ _.role("user") }}
    Query: {{ query }}
    Memories Store: {{ memories_store }}
  "#
}


class MemoriesStore {
  description string @description("The description of the memory")
  image_index int @description("The index of the image in the images store")
}

class SelectMemoryResponse {
  selected_memories_summary string @description("The description of the selected memories")
  image_index_list int[] @description("The list of index of the images in the images store")
}