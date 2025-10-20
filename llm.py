from typing import List, Tuple, Dict, Any


def _format_memories(memories: List[Tuple[Dict[str, Any], float]]) -> str:
	lines = []
	for i, (m, score) in enumerate(memories, start=1):
		text = m.get("text", "").strip()
		lines.append(f"{i}. {text}")
	return "\n".join(lines)


def generate_response(
	user_message: str,
	memories: List[Tuple[Dict[str, Any], float]],
	model: str = "llama3.2",
	temperature: float = 0.4,
	max_tokens: int = 512,
) -> str:
	"""Generate a supportive response.

	Attempts to use local Ollama. If unavailable, falls back to a simple
	template-based response that references retrieved memories.
	"""
	context_block = _format_memories(memories)
	prompt = (
		"You are a supportive mental health companion. Be warm, brief, and practical.\n"
		"Use the user's positive memories below to help them recall strengths and moments of joy.\n"
		"Avoid medical claims; suggest gentle actions like breathing, a short walk, or recalling a favorite memory.\n\n"
		"Positive memories:\n" + context_block + "\n\n"
		"User: " + user_message.strip() + "\n"
		"Assistant:"
	)

	# Try Ollama if available
	try:
		import ollama  # type: ignore

		messages = [
			{"role": "system", "content": "You are a supportive mental health companion."},
			{"role": "user", "content": prompt},
		]
		resp = ollama.chat(model=model, messages=messages, options={"temperature": temperature, "num_predict": max_tokens})
		text = resp.get("message", {}).get("content")
		if isinstance(text, str) and text.strip():
			return text.strip()
	except Exception:
		pass

	# Fallback minimal response
	if context_block.strip():
		return (
			"I'm here with you. From your memories, these moments stood out:\n"
			+ context_block
			+ "\nWould revisiting one of them help right now? Maybe look at a photo, write a few lines about it, or take a few slow breaths while remembering how it felt."
		)
	return (
		"I'm here with you. Let's take one small step together: try a slow inhale for 4, hold for 4, and exhale for 6. If you'd like, tell me about a moment that once made you feel safe or proud, and we can explore it together."
	)
