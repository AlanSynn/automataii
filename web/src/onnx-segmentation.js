export const BODY_PART_ORDER = [
  "head",
  "torso",
  "upper_arm_left",
  "lower_arm_left",
  "upper_arm_right",
  "lower_arm_right",
  "upper_leg_left",
  "lower_leg_left",
  "upper_leg_right",
  "lower_leg_right",
];

const MODEL_INPUT_SIZE = 256;

export async function loadOnnxSegmenter({ modelBuffer, modelUrl, executionProvider = "wasm", inputSize = MODEL_INPUT_SIZE } = {}) {
  if (!modelBuffer && !modelUrl) throw new Error("Load an ONNX model file or URL first.");
  const { ort, baseUrl } = await loadOrt();
  ort.env.wasm ||= {};
  ort.env.wasm.wasmPaths = baseUrl;
  const session = await ort.InferenceSession.create(modelBuffer || modelUrl, {
    executionProviders: [executionProvider],
  });
  return {
    inputSize,
    inputNames: session.inputNames || [],
    outputNames: session.outputNames || [],
    async segment(imageSrc) {
      const image = await imageToTensor(ort, imageSrc, inputSize);
      const inputName = session.inputNames?.[0];
      if (!inputName) throw new Error("ONNX model has no image input.");
      const outputs = await session.run({ [inputName]: image.tensor });
      return postprocessOnnxOutputs(outputs, image.width, image.height);
    },
  };
}

export function postprocessOnnxOutputs(outputs, imageWidth, imageHeight) {
  const boxOutput = findBoxOutput(outputs);
  if (boxOutput) return boxesToParts(boxOutput, imageWidth, imageHeight);
  const maskOutput = findMaskOutput(outputs);
  if (maskOutput) return splitBodyBox(maskToBox(maskOutput, imageWidth, imageHeight));
  throw new Error("ONNX output did not include recognizable boxes or masks.");
}

export function splitBodyBox(box) {
  const [x, y, w, h] = box.map((value) => Math.max(0, Number(value) || 0));
  if (!w || !h) return {};
  return {
    head: [x + w * 0.35, y, w * 0.3, h * 0.16],
    torso: [x + w * 0.25, y + h * 0.16, w * 0.5, h * 0.34],
    upper_arm_left: [x, y + h * 0.18, w * 0.25, h * 0.22],
    lower_arm_left: [x, y + h * 0.38, w * 0.22, h * 0.22],
    upper_arm_right: [x + w * 0.75, y + h * 0.18, w * 0.25, h * 0.22],
    lower_arm_right: [x + w * 0.78, y + h * 0.38, w * 0.22, h * 0.22],
    upper_leg_left: [x + w * 0.25, y + h * 0.50, w * 0.22, h * 0.26],
    lower_leg_left: [x + w * 0.22, y + h * 0.74, w * 0.22, h * 0.26],
    upper_leg_right: [x + w * 0.53, y + h * 0.50, w * 0.22, h * 0.26],
    lower_leg_right: [x + w * 0.56, y + h * 0.74, w * 0.22, h * 0.26],
  };
}

async function loadOrt() {
  const candidates = [
    "../vendor/onnxruntime-web/ort.all.min.mjs",
    "../node_modules/onnxruntime-web/dist/ort.all.min.mjs",
  ];
  let lastError;
  for (const path of candidates) {
    try {
      const mod = await import(path);
      return { ort: mod, baseUrl: new URL(path.replace(/[^/]+$/, ""), import.meta.url).href };
    } catch (error) {
      lastError = error;
    }
  }
  throw new Error(`ONNX Runtime Web unavailable. Run npm install. ${lastError?.message || ""}`);
}

async function imageToTensor(ort, imageSrc, size) {
  const image = await loadImage(imageSrc);
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(image, 0, 0, size, size);
  const pixels = ctx.getImageData(0, 0, size, size).data;
  const data = new Float32Array(3 * size * size);
  for (let i = 0, p = 0; i < pixels.length; i += 4, p += 1) {
    data[p] = pixels[i] / 255;
    data[size * size + p] = pixels[i + 1] / 255;
    data[2 * size * size + p] = pixels[i + 2] / 255;
  }
  return {
    tensor: new ort.Tensor("float32", data, [1, 3, size, size]),
    width: image.naturalWidth || image.width || size,
    height: image.naturalHeight || image.height || size,
  };
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Could not decode image for ONNX inference."));
    image.src = src;
  });
}

function findBoxOutput(outputs) {
  for (const value of Object.values(outputs || {})) {
    if (value?.dims?.length === 2 && value.dims[1] >= 4 && value.data?.length >= 4) return value;
  }
  return null;
}

function findMaskOutput(outputs) {
  let best = null;
  for (const value of Object.values(outputs || {})) {
    if (value?.dims?.length >= 2 && value.data?.length > (best?.data?.length || 0)) best = value;
  }
  return best;
}

function boxesToParts(output, imageWidth, imageHeight) {
  const stride = output.dims[1];
  const boxes = {};
  for (let row = 0; row < output.dims[0] && row < BODY_PART_ORDER.length; row += 1) {
    const offset = row * stride;
    let [x1, y1, x2, y2] = Array.from(output.data.slice(offset, offset + 4), Number);
    if (Math.max(x1, y1, x2, y2) <= 1.5) {
      x1 *= imageWidth; x2 *= imageWidth; y1 *= imageHeight; y2 *= imageHeight;
    }
    boxes[BODY_PART_ORDER[row]] = [Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1)];
  }
  return boxes;
}

function maskToBox(output, imageWidth, imageHeight) {
  const dims = output.dims;
  const width = dims[dims.length - 1];
  const height = dims[dims.length - 2];
  const data = output.data;
  const max = data.reduce((m, value) => Math.max(m, Number(value) || 0), -Infinity);
  const min = data.reduce((m, value) => Math.min(m, Number(value) || 0), Infinity);
  const threshold = min + (max - min) * 0.45;
  let left = width, top = height, right = 0, bottom = 0;
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if ((Number(data[y * width + x]) || 0) <= threshold) continue;
      left = Math.min(left, x); top = Math.min(top, y); right = Math.max(right, x); bottom = Math.max(bottom, y);
    }
  }
  if (left > right || top > bottom) return [imageWidth * 0.2, imageHeight * 0.05, imageWidth * 0.6, imageHeight * 0.9];
  return [
    (left / width) * imageWidth,
    (top / height) * imageHeight,
    ((right - left + 1) / width) * imageWidth,
    ((bottom - top + 1) / height) * imageHeight,
  ];
}
