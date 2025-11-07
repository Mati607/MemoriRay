function  ImageDescription(image_b64: image) -> string {
  client "GeminiFlashImage"
  prompt #"
    {{ _.role("system") }}
    You are a image description generator. You will be given a image and you will need to generate a description of the image. Do not make the description too long. Just give a brief description of the image to help the user remember it and understand the context of the image.
    {{ _.role("user") }}
    {{ image_b64 }}
  "#
}