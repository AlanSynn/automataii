import { useCallback, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import type { InferenceSession } from 'onnxruntime-web'

import type { SerializedTensor, TensorSpec } from '../../infra/onnx/onnxRuntime'
import { OnnxWorkerClient, type SessionMetadata } from '../../infra/onnx'

export type OnnxStatus = 'idle' | 'loading' | 'ready' | 'running' | 'error'

export interface OnnxModelState {
  status: OnnxStatus
  metadata: SessionMetadata | null
  outputs: Record<string, SerializedTensor> | null
  error: string | null
  modelName: string | null
}

const defaultState: OnnxModelState = {
  status: 'idle',
  metadata: null,
  outputs: null,
  error: null,
  modelName: null,
}

export interface OnnxModelController {
  state: OnnxModelState
  loadModel: (event: ChangeEvent<HTMLInputElement>) => void
  runInference: (feedsJson: string) => Promise<void>
  reset: () => void
}

export const useOnnxModel = (): OnnxModelController => {
  const [state, setState] = useState<OnnxModelState>(defaultState)
  const clientRef = useRef<OnnxWorkerClient | null>(null)

  const reset = useCallback(() => {
    clientRef.current?.terminate()
    clientRef.current = null
    setState(defaultState)
  }, [])

  const loadModel = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0]
      if (!file) {
        reset()
        return
      }
      setState({
        status: 'loading',
        metadata: null,
        outputs: null,
        error: null,
        modelName: file.name,
      })
      const client = new OnnxWorkerClient()
      clientRef.current = client
      file
        .arrayBuffer()
        .then((buffer) =>
          client.init(buffer, defaultSessionOptions(), '/')
        )
        .then((metadata) => {
          setState({
            status: 'ready',
            metadata,
            outputs: null,
            error: null,
            modelName: file.name,
          })
        })
        .catch((error: unknown) => {
          setState({
            status: 'error',
            metadata: null,
            outputs: null,
            error: error instanceof Error ? error.message : 'Failed to load model',
            modelName: file.name,
          })
        })
    },
    [reset]
  )

  const runInference = useCallback(async (feedsJson: string) => {
    const client = clientRef.current
    if (!client) {
      setState((current) => ({
        ...current,
        status: 'error',
        error: 'Model is not loaded.',
      }))
      return
    }
    const parsed = parseFeedsJson(feedsJson)
    if (!parsed.success) {
      setState((current) => ({
        ...current,
        status: 'error',
        error: parsed.error,
      }))
      return
    }
    setState((current) => ({ ...current, status: 'running', error: null }))
    try {
      const outputs = await client.run(parsed.feeds)
      setState((current) => ({
        ...current,
        status: 'ready',
        outputs,
        error: null,
      }))
    } catch (error) {
      setState((current) => ({
        ...current,
        status: 'error',
        error: error instanceof Error ? error.message : 'Inference failed',
      }))
    }
  }, [])

  return { state, loadModel, runInference, reset }
}

interface ParseResultSuccess {
  success: true
  feeds: TensorSpec[]
}

interface ParseResultError {
  success: false
  error: string
}

type ParseResult = ParseResultSuccess | ParseResultError

const parseFeedsJson = (contents: string): ParseResult => {
  let parsed: unknown
  try {
    parsed = JSON.parse(contents)
  } catch (error) {
    return { success: false, error: errorMessage(error) }
  }
  if (!isRecord(parsed)) {
    return { success: false, error: 'Feeds must be an object.' }
  }
  const feeds: TensorSpec[] = []
  for (const [name, value] of Object.entries(parsed)) {
    if (!isRecord(value)) {
      return { success: false, error: `Feed ${name} must be an object.` }
    }
    const specResult = buildTensorSpec(name, value)
    if (!specResult.success) {
      return specResult
    }
    feeds.push(specResult.feed)
  }
  return { success: true, feeds }
}

const buildTensorSpec = (
  name: string,
  raw: Record<string, unknown>
): { success: true; feed: TensorSpec } | { success: false; error: string } => {
  const type = typeof raw.type === 'string' ? raw.type : 'float32'
  if (!Array.isArray(raw.dims)) {
    return { success: false, error: `Feed ${name} dims must be an array.` }
  }
  const dims = raw.dims.map((value) => Number(value))
  if (dims.some((value) => !Number.isFinite(value))) {
    return { success: false, error: `Feed ${name} dims must be numbers.` }
  }
  if (!Array.isArray(raw.data)) {
    return { success: false, error: `Feed ${name} data must be an array.` }
  }
  const data = raw.data.map((value) => (typeof value === 'number' || typeof value === 'string' ? value : 0))
  const expectedLength = dims.reduce((total, value) => total * value, 1)
  if (expectedLength > 0 && data.length !== expectedLength) {
    return {
      success: false,
      error: `Feed ${name} data length ${data.length} does not match dims (${expectedLength}).`,
    }
  }
  const typedData = coerceTensorData(type, data)
  return {
    success: true,
    feed: {
      name,
      data: typedData,
      dims,
      type: normalizeTensorType(type),
    },
  }
}

const coerceTensorData = (type: string, data: Array<number | string>): TensorSpec['data'] => {
  switch (normalizeTensorType(type)) {
    case 'float32':
      return new Float32Array(data.map((value) => Number(value)))
    case 'int32':
      return new Int32Array(data.map((value) => Number(value)))
    case 'uint8':
      return new Uint8Array(data.map((value) => Number(value)))
    case 'int64':
      return new BigInt64Array(
        data.map((value) => BigInt(typeof value === 'string' ? value : Math.trunc(value)))
      )
    default:
      return new Float32Array(data.map((value) => Number(value)))
  }
}

const normalizeTensorType = (type: string): TensorSpec['type'] => {
  if (type === 'float32' || type === 'int32' || type === 'uint8' || type === 'int64') {
    return type
  }
  return 'float32'
}

const defaultSessionOptions = (): InferenceSession.SessionOptions => ({
  executionProviders: ['webgpu', 'wasm'],
})

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const errorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message
  }
  return 'Unknown error'
}
