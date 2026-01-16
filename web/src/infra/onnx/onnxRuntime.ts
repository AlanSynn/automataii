import * as ort from 'onnxruntime-web'

export interface TensorSpec {
  name: string
  data: ort.Tensor.DataType
  dims: number[]
  type?: ort.Tensor.Type
}

export interface SerializedTensor {
  name: string
  dims: number[]
  type: ort.Tensor.Type
  data: Array<number | string>
}

export interface SessionConfig {
  wasmPaths?: string
  sessionOptions?: ort.InferenceSession.SessionOptions
}

export const configureOrt = (wasmPaths: string): void => {
  ort.env.wasm.wasmPaths = wasmPaths
}

export const createTensor = (spec: TensorSpec): ort.Tensor => {
  const type = spec.type ?? inferTensorType(spec.data)
  return new ort.Tensor(type, spec.data, spec.dims)
}

export const createSession = async (
  model: ArrayBuffer,
  config: SessionConfig = {}
): Promise<ort.InferenceSession> => {
  if (config.wasmPaths) {
    configureOrt(config.wasmPaths)
  }
  return ort.InferenceSession.create(model, config.sessionOptions)
}

export const runSession = async (
  session: ort.InferenceSession,
  feeds: TensorSpec[]
): Promise<Record<string, SerializedTensor>> => {
  const feedTensors: Record<string, ort.Tensor> = {}
  feeds.forEach((feed) => {
    feedTensors[feed.name] = createTensor(feed)
  })
  const outputs = await session.run(feedTensors)
  const serialized: Record<string, SerializedTensor> = {}
  Object.entries(outputs).forEach(([name, tensor]) => {
    serialized[name] = serializeTensor(name, tensor)
  })
  return serialized
}

const serializeTensor = (name: string, tensor: ort.Tensor): SerializedTensor => {
  const data = tensor.data
  const entries: Array<number | string> = []
  if (Array.isArray(data)) {
    data.forEach((value) => entries.push(normalizeTensorValue(value)))
  } else {
    Array.from(data as ArrayLike<number | bigint>).forEach((value) => {
      entries.push(normalizeTensorValue(value))
    })
  }
  return {
    name,
    dims: [...tensor.dims],
    type: tensor.type,
    data: entries,
  }
}

const normalizeTensorValue = (value: number | bigint | string): number | string =>
  typeof value === 'bigint' ? value.toString() : value

const inferTensorType = (data: ort.Tensor.DataType): ort.Tensor.Type => {
  if (data instanceof Float32Array) {
    return 'float32'
  }
  if (data instanceof Uint8Array) {
    return 'uint8'
  }
  if (data instanceof Int32Array) {
    return 'int32'
  }
  if (data instanceof BigInt64Array) {
    return 'int64'
  }
  return 'float32'
}
