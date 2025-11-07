function  ImageDescription(image_b64: image) -> string {
  client "GeminiDefault"
  prompt #"
    {{ _.role("system") }}
    You are a image description generator. You will be given a image and you will need to generate a description of the image.
    {{ _.role("user") }}
    {{ image_b64 }}
  "#
}