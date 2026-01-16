import * as ort from 'onnxruntime-web'

interface InitMessage {
  type: 'init'
  modelBuffer: ArrayBuffer
  sessionOptions?: ort.InferenceSession.SessionOptions
  wasmPaths?: string
}

interface RunMessage {
  type: 'run'
  feeds: SerializedTensorSpec[]
}

interface SerializedTensorSpec {
  name: string
  type: ort.Tensor.Type
  dims: number[]
  data: Array<number | string>
}

type WorkerMessage = InitMessage | RunMessage

interface ValueMetadata {
  name: string
  isTensor: boolean
  type?: ort.Tensor.Type
  shape?: Array<number | string>
}

interface SessionMetadata {
  inputNames: readonly string[]
  outputNames: readonly string[]
  inputMetadata: ValueMetadata[]
  outputMetadata: ValueMetadata[]
}

type WorkerResponse =
  | { type: 'ready'; metadata: SessionMetadata }
  | { type: 'result'; outputs: Record<string, SerializedTensorSpec> }
  | { type: 'error'; error: string }

let session: ort.InferenceSession | null = null

const postResponse = (response: WorkerResponse): void => {
  self.postMessage(response)
}

const toTensorData = (spec: SerializedTensorSpec): ort.Tensor.DataType => {
  switch (spec.type) {
    case 'float32':
      return new Float32Array(spec.data.map((value) => Number(value)))
    case 'int32':
      return new Int32Array(spec.data.map((value) => Number(value)))
    case 'uint8':
      return new Uint8Array(spec.data.map((value) => Number(value)))
    case 'int64':
      return new BigInt64Array(
        spec.data.map((value) => BigInt(typeof value === 'string' ? value : Math.trunc(value)))
      )
    default:
      return new Float32Array(spec.data.map((value) => Number(value)))
  }
}

const toTensor = (spec: SerializedTensorSpec): ort.Tensor => {
  const data = toTensorData(spec)
  return new ort.Tensor(spec.type, data, spec.dims)
}

const serializeTensor = (name: string, tensor: ort.Tensor): SerializedTensorSpec => {
  const entries: Array<number | string> = []
  const data = tensor.data
  if (Array.isArray(data)) {
    data.forEach((value) => entries.push(normalizeTensorValue(value)))
  } else {
    Array.from(data as ArrayLike<number | bigint>).forEach((value) => {
      entries.push(normalizeTensorValue(value))
    })
  }
  return {
    name,
    type: tensor.type,
    dims: [...tensor.dims],
    data: entries,
  }
}

const serializeMetadata = (metadata: ort.InferenceSession.ValueMetadata): ValueMetadata => {
  if (!metadata.isTensor) {
    return { name: metadata.name, isTensor: false }
  }
  return {
    name: metadata.name,
    isTensor: true,
    type: metadata.type,
    shape: [...metadata.shape],
  }
}

const serializeSessionMetadata = (target: ort.InferenceSession): SessionMetadata => ({
  inputNames: [...target.inputNames],
  outputNames: [...target.outputNames],
  inputMetadata: target.inputMetadata.map((entry) => serializeMetadata(entry)),
  outputMetadata: target.outputMetadata.map((entry) => serializeMetadata(entry)),
})

const normalizeTensorValue = (value: number | bigint | string): number | string =>
  typeof value === 'bigint' ? value.toString() : value

self.onmessage = async (event: MessageEvent<WorkerMessage>): Promise<void> => {
  try {
    if (event.data.type === 'init') {
      if (event.data.wasmPaths) {
        ort.env.wasm.wasmPaths = event.data.wasmPaths
      }
      session = await ort.InferenceSession.create(
        event.data.modelBuffer,
        event.data.sessionOptions
      )
      const metadata = serializeSessionMetadata(session)
      postResponse({ type: 'ready', metadata })
      return
    }

    if (event.data.type === 'run') {
      if (!session) {
        postResponse({ type: 'error', error: 'Session not initialized.' })
        return
      }
      const feeds: Record<string, ort.Tensor> = {}
      event.data.feeds.forEach((spec) => {
        feeds[spec.name] = toTensor(spec)
      })
      const outputs = await session.run(feeds)
      const serialized: Record<string, SerializedTensorSpec> = {}
      Object.entries(outputs).forEach(([name, tensor]) => {
        serialized[name] = serializeTensor(name, tensor)
      })
      postResponse({ type: 'result', outputs: serialized })
    }
  } catch (error) {
    postResponse({ type: 'error', error: error instanceof Error ? error.message : 'Unknown error' })
  }
}
