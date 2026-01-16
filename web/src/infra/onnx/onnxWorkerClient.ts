import type { InferenceSession } from 'onnxruntime-web'

import type { SerializedTensor, TensorSpec } from './onnxRuntime'

export interface SessionMetadataEntry {
  name: string
  isTensor: boolean
  type?: string
  shape?: Array<number | string>
}

export interface SessionMetadata {
  inputNames: readonly string[]
  outputNames: readonly string[]
  inputMetadata: SessionMetadataEntry[]
  outputMetadata: SessionMetadataEntry[]
}

interface WorkerReadyMessage {
  type: 'ready'
  metadata: SessionMetadata
}

interface SerializedTensorSpec {
  name: string
  type: string
  dims: number[]
  data: Array<number | string>
}

interface WorkerResultMessage {
  type: 'result'
  outputs: Record<string, SerializedTensor>
}

interface WorkerErrorMessage {
  type: 'error'
  error: string
}

type WorkerResponse = WorkerReadyMessage | WorkerResultMessage | WorkerErrorMessage

export class OnnxWorkerClient {
  private worker: Worker
  private readyResolver: ((value: SessionMetadata) => void) | null = null
  private readyRejecter: ((reason?: unknown) => void) | null = null
  private pendingResolver: ((value: Record<string, SerializedTensor>) => void) | null = null
  private pendingRejecter: ((reason?: unknown) => void) | null = null

  constructor() {
    this.worker = new Worker(new URL('./onnxWorker.ts', import.meta.url), {
      type: 'module',
    })
    this.worker.onmessage = (event: MessageEvent<WorkerResponse>) => {
      this.handleMessage(event.data)
    }
  }

  async init(
    model: ArrayBuffer,
    options?: InferenceSession.SessionOptions,
    wasmPaths?: string
  ): Promise<SessionMetadata> {
    if (this.readyResolver) {
      throw new Error('Worker is already initializing.')
    }
    const readyPromise = new Promise<SessionMetadata>((resolve, reject) => {
      this.readyResolver = resolve
      this.readyRejecter = reject
    })
    this.worker.postMessage({
      type: 'init',
      modelBuffer: model,
      sessionOptions: options,
      wasmPaths,
    })
    return readyPromise
  }

  async run(feeds: TensorSpec[]): Promise<Record<string, SerializedTensor>> {
    if (this.pendingResolver) {
      throw new Error('Worker already running inference.')
    }
    const runPromise = new Promise<Record<string, SerializedTensor>>((resolve, reject) => {
      this.pendingResolver = resolve
      this.pendingRejecter = reject
    })
    const serializedFeeds = feeds.map((feed) => serializeFeed(feed))
    this.worker.postMessage({ type: 'run', feeds: serializedFeeds })
    return runPromise
  }

  terminate(): void {
    this.worker.terminate()
  }

  private handleMessage(message: WorkerResponse): void {
    if (message.type === 'ready') {
      this.readyResolver?.(message.metadata)
      this.readyResolver = null
      this.readyRejecter = null
      return
    }
    if (message.type === 'result') {
      this.pendingResolver?.(message.outputs)
      this.pendingResolver = null
      this.pendingRejecter = null
      return
    }
    if (message.type === 'error') {
      const error = new Error(message.error)
      if (this.pendingRejecter) {
        this.pendingRejecter(error)
        this.pendingResolver = null
        this.pendingRejecter = null
        return
      }
      if (this.readyRejecter) {
        this.readyRejecter(error)
        this.readyResolver = null
        this.readyRejecter = null
      }
    }
  }
}

const serializeFeed = (feed: TensorSpec): SerializedTensorSpec => ({
  name: feed.name,
  type: feed.type ?? 'float32',
  dims: [...feed.dims],
  data: Array.from(feed.data as ArrayLike<number | bigint>).map((value) =>
    typeof value === 'bigint' ? value.toString() : value
  ),
})
