import { Box, ImagePlus, Leaf, LoaderCircle, Search, Sparkles, TrendingUp } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAnalyzeReturn, useApproveReturn, useDeleteReturn, usePredictCondition, useRejectReturn, useReturns } from '../hooks/useReturns'
import { useSettings } from '../hooks/useSettings'
import { getProductValidationMessage, getVerifiedProductValidation, PRODUCT_MIN_CONFIDENCE } from '../utils/approvalValidation'
import { beginValidationRequest, isCurrentValidationRequest } from '../utils/validationRequestSequence'
import { api } from '../services/api'
import DecisionBadge from '../components/DecisionBadge'
import ErrorCard from '../components/ErrorCard'
import Skeleton from '../components/Skeleton'

const conditionOptions = ['Damaged', 'Bad', 'Fair', 'Good']
const EMPTY_RETURNS = []

const defaultForm = {
  condition: '',
  condition_score: 75,
  notes: '',
  image: null,
}

export default function ProcessReturns() {
  const [params] = useSearchParams()
  const requestedId = Number(params.get('selected'))
  const querySelectedId = Number.isInteger(requestedId) && requestedId > 0 ? requestedId : null
  const [status, setStatus] = useState('all')
  const [search, setSearch] = useState('')
  const { data: queryData, isLoading, error, refetch } = useReturns(status)
  const { data: decisionSettings } = useSettings()
  const data = Array.isArray(queryData) ? queryData : EMPTY_RETURNS
  const [manuallySelectedId, setManuallySelectedId] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const analyze = useAnalyzeReturn()
  const predictCondition = usePredictCondition()
  const approve = useApproveReturn()
  const reject = useRejectReturn()
  const remove = useDeleteReturn()

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return data.filter((item) => item && String(item.product_name ?? '').toLowerCase().includes(q))
  }, [data, search])

  const requestedSelectedId = manuallySelectedId ?? querySelectedId
  const selected = filtered.find((item) => item.id === requestedSelectedId) || filtered[0] || null
  const selectedId = selected?.id ?? null
  const selectedKey = selected
    ? `${selected.id}|${selected.analyzed_at || ''}|${selected.processed_at || ''}|${selected.notes || ''}|${selected.condition || ''}|${selected.condition_score ?? ''}|${selected.condition_confidence ?? ''}|${selected.image_path || ''}|${selected.product_validation || ''}|${selected.product_matches ?? ''}|${selected.status}`
    : ''
  const [assessmentState, setAssessmentState] = useState(null)
  const [isDraggingImage, setIsDraggingImage] = useState(false)
  const createCurrentAssessment = () => createAssessmentState(selectedKey, selected)
  const activeAssessment = assessmentState?.key === selectedKey ? assessmentState : createCurrentAssessment()
  const { form, scoreOverride, predictionMeta, analysisResult, assessmentDirty, imageError, approvalError } = activeAssessment
  const updateAssessment = (updater) => {
    setAssessmentState((current) => {
      const base = current?.key === selectedKey ? current : createCurrentAssessment()
      const changes = typeof updater === 'function' ? updater(base) : updater
      return { ...base, ...changes, key: selectedKey }
    })
  }
  const setForm = (updater) => updateAssessment((current) => ({
    form: typeof updater === 'function' ? updater(current.form) : updater,
  }))
  const setScoreOverride = (value) => updateAssessment({ scoreOverride: value })
  const setPredictionMeta = (value) => updateAssessment({ predictionMeta: value })
  const setAnalysisResult = (value) => updateAssessment({ analysisResult: value })
  const setAssessmentDirty = (value) => updateAssessment({ assessmentDirty: value })
  const setImageError = (value) => updateAssessment({ imageError: value })
  const setApprovalError = (value) => updateAssessment({ approvalError: value })
  const selectedAnalysis = assessmentDirty
    ? (analysisResult && analysisResult.id === selected?.id ? analysisResult.data : null)
    : (analysisResult && analysisResult.id === selected?.id ? analysisResult.data : selected)
  const predictionRequestId = useRef(0)
  const imageInputRef = useRef(null)
  const imagePreviewUrl = imagePreview?.selectedId === selectedId ? imagePreview.url : null
  const selectedImageUrl = imagePreviewUrl || getReturnImageUrl(selected?.image_path)
  const imageUploadDisabled = analyze.isPending || predictCondition.isPending

  useEffect(() => {
    beginValidationRequest(predictionRequestId)
  }, [selectedId])

  useEffect(() => () => {
    if (imagePreview?.url) URL.revokeObjectURL(imagePreview.url)
  }, [imagePreview?.url, selectedId])
  const needsManualReview = Boolean(selectedAnalysis?.needs_manual_review)
    || (selectedAnalysis?.confidence_score != null && Number(selectedAnalysis.confidence_score) < 60)
  const displayedDecision = formatDecision(
    selectedAnalysis?.recommended_decision,
    needsManualReview,
    selectedAnalysis?.confidence_score,
  )
  const productValidation = form.image
    ? getVerifiedProductValidation(predictionMeta, selected?.expected_product)
    : assessmentDirty
      ? 'UNVERIFIED'
      : getVerifiedProductValidation(selectedAnalysis, selected?.expected_product)
  const productValidationMessage = getProductValidationMessage(productValidation)
  const hasSuccessfulInference = Boolean(
    predictionMeta &&
    predictionMeta.condition &&
    Number.isFinite(Number(predictionMeta.condition_score)) &&
    Number.isFinite(Number(predictionMeta.confidence)) &&
    predictionMeta.product_validation === 'MATCH' &&
    Number(predictionMeta.product_confidence) >= PRODUCT_MIN_CONFIDENCE,
  )
  const analysisBlockedReason = imageError
    || (productValidation === 'MISMATCH'
      ? 'Product mismatch: upload an image of the selected return product.'
      : productValidation === 'UNVERIFIED'
        ? 'Product unverified: the image could not be reliably identified.'
        : 'Upload and successfully verify an image before analyzing.')
  const hasSavedAssessment = Boolean(
    selected?.analyzed_at &&
    selected?.condition &&
    selected?.condition_score != null &&
    selected?.recommended_decision,
  )
  const assessmentReady = Boolean(
    !assessmentDirty &&
    (hasSavedAssessment || analysisResult?.id === selected?.id),
  )
  const approvalBlockedReason = getApprovalBlockedReason({
    selected,
    assessment: selectedAnalysis,
    assessmentReady,
    notes: form.notes,
    productValidation,
  })
  const approvalWarnings = getApprovalWarnings(selected, selectedAnalysis, decisionSettings)

  const applyPrediction = (prediction) => {
    const safePrediction = {
      ...prediction,
      product_validation: getVerifiedProductValidation(prediction, selected?.expected_product),
    }
    setForm((previous) => ({
      ...previous,
      condition: toAssessmentCondition(safePrediction.condition),
      condition_score: safePrediction.condition_score,
    }))
    setScoreOverride(false)
    setPredictionMeta(safePrediction)
    setAssessmentDirty(true)
    setAnalysisResult(null)
  }

  const requestConditionPrediction = async (file) => {
    const requestId = beginValidationRequest(predictionRequestId)
    setImageError('')
    try {
      const prediction = await predictCondition.mutateAsync({ id: selected?.id, image: file })
      if (isCurrentValidationRequest(predictionRequestId, requestId)) applyPrediction(prediction)
    } catch (requestError) {
      if (isCurrentValidationRequest(predictionRequestId, requestId)) {
        setImageError(requestError.message || 'Image analysis failed. Retry or assess the condition manually.')
      }
    }
  }

  const onImageSelected = async (file) => {
    beginValidationRequest(predictionRequestId)
    setIsDraggingImage(false)
    setForm((previous) => ({ ...previous, image: file || null }))
    setImagePreview(null)
    setPredictionMeta(null)
    setScoreOverride(false)
    setAssessmentDirty(Boolean(file))
    setAnalysisResult(null)
    setImageError('')
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setForm((previous) => ({ ...previous, image: null }))
      setImagePreview(null)
      setImageError('Choose a supported image file.')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setForm((previous) => ({ ...previous, image: null }))
      setImageError('Image must be 10 MB or smaller.')
      return
    }
    setImagePreview({ selectedId, url: URL.createObjectURL(file) })
    await requestConditionPrediction(file)
  }

  const onImageDragEnter = (event) => {
    event.preventDefault()
    event.stopPropagation()
    if (imageUploadDisabled) return
    if (Array.from(event.dataTransfer?.types || []).includes('Files')) setIsDraggingImage(true)
  }

  const onImageDragOver = (event) => {
    event.preventDefault()
    event.stopPropagation()
    if (imageUploadDisabled) return
    event.dataTransfer.dropEffect = 'copy'
    if (!isDraggingImage) setIsDraggingImage(true)
  }

  const onImageDragLeave = (event) => {
    event.preventDefault()
    event.stopPropagation()
    if (event.currentTarget.contains(event.relatedTarget)) return
    setIsDraggingImage(false)
  }

  const onImageDrop = (event) => {
    event.preventDefault()
    event.stopPropagation()
    setIsDraggingImage(false)
    if (imageUploadDisabled) return
    const file = event.dataTransfer?.files?.[0] || null
    void onImageSelected(file)
  }

  const onAnalyze = async () => {
    if (!selected) return
    if (!hasSuccessfulInference || !form.image || predictCondition.isPending) {
      setImageError(analysisBlockedReason)
      return
    }
    const payload = new FormData()
    Object.entries(form).forEach(([key, value]) => {
      if (key === 'image') {
        if (value) payload.append('image', value)
      } else if (key === 'notes') {
        payload.append(key, value.trim())
      } else {
        payload.append(key, value)
      }
    })
    payload.append('score_override', 'false')
    const requestId = beginValidationRequest(predictionRequestId)
    const itemBeingAnalyzed = selected
    setAssessmentDirty(true)
    try {
      const analysis = await analyze.mutateAsync({ id: itemBeingAnalyzed.id, formData: payload })
      if (!isCurrentValidationRequest(predictionRequestId, requestId)) return
      const safeAnalysis = {
        ...(analysis && typeof analysis === 'object' ? analysis : {}),
        product_validation: getVerifiedProductValidation(analysis, itemBeingAnalyzed.expected_product),
      }
      setAnalysisResult({ id: itemBeingAnalyzed.id, data: safeAnalysis })
      if (analysis?.condition) {
        setForm((previous) => ({
          ...previous,
          condition: toAssessmentCondition(analysis.condition),
          condition_score: analysis.adjusted_condition_score,
        }))
        setPredictionMeta({
          condition: analysis.condition,
          condition_score: analysis.ai_score ?? analysis.adjusted_condition_score,
          confidence: analysis.condition_confidence,
          product_label: analysis.product_label,
          product_confidence: analysis.product_confidence,
          product_matches: analysis.product_matches,
          product_validation: safeAnalysis.product_validation,
          expected_product: analysis.expected_product,
          model_name: analysis.model_name,
          source: analysis.score_source,
        })
        setScoreOverride(analysis.score_source === 'inspector_override')
      }
      setAssessmentDirty(false)
      setApprovalError('')
      await refetch()
    } catch {
      // Mutation errors are shown by the API hook.
    }
  }

  const onFinalize = async (decision) => {
    setApprovalError('')
    if (decision === 'approved' && approvalBlockedReason) {
      setApprovalError(approvalBlockedReason)
      return
    }
    if (!form.notes.trim()) return setApprovalError("Inspector's Note is required before finalizing this return.")
    if (!assessmentReady) return setApprovalError('Analyze the current condition assessment before finalizing this return.')
    if (selected.status !== 'pending') return setApprovalError('This return has already been processed.')
    const payload = { notes: form.notes.trim() }
    try {
      await (decision === 'approved' ? approve : reject).mutateAsync({ id: selected.id, payload })
      await refetch()
    } catch (requestError) {
      setApprovalError(requestError.message || 'Unable to finalize this return.')
    }
  }

  if (isLoading) {
    return <div className="grid h-full min-h-0 grid-cols-5 gap-4 max-lg:h-auto max-lg:grid-cols-1"><Skeleton className="col-span-2 h-full min-h-[320px] max-lg:col-span-1 max-lg:h-[calc(100dvh-108px)]" /><Skeleton className="col-span-3 h-full min-h-[320px] max-lg:col-span-1 max-lg:h-[calc(100dvh-108px)]" /></div>
  }

  if (error) {
    return <ErrorCard message="Unable to load return queue." onRetry={refetch} />
  }

  const scoreHint = predictCondition.isPending
    ? 'Scoring product image…'
    : predictionMeta
      ? scoreOverride
        ? 'Inspector override active — model suggestion kept for reference.'
        : predictionMeta.product_label
          ? `${predictionMeta.product_label} — ${predictionMeta.product_confidence == null ? '--' : `${Math.round(predictionMeta.product_confidence)}%`}`
          : predictionMeta.confidence == null ? 'Manual assessment' : `Model confidence ${Math.round(predictionMeta.confidence)}%`
      : 'Upload a product photo to auto-fill the score, or set it manually.'

  return (
    <div className="grid h-full min-h-0 grid-cols-5 gap-4 max-lg:h-auto max-lg:grid-cols-1">
      <section className="col-span-2 flex min-h-0 flex-col overflow-hidden rounded-xl border p-4 max-lg:col-span-1 max-lg:h-[calc(100dvh-108px)]" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Returns Queue</h2>
          <span className="rounded-full px-3 py-1 text-xs" style={{ background: 'var(--bg-elevated)' }}>{filtered.length}</span>
        </div>
        <div className="mb-3 flex items-center gap-2 rounded-xl border px-3" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-elevated)' }}>
          <Search size={16} />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by product name" className="h-11 w-full border-none bg-transparent outline-none" />
        </div>
        <div className="mb-4 flex gap-2 overflow-auto">
          {['all', 'pending', 'approved', 'rejected'].map((key) => (
            <button key={key} type="button" onClick={() => setStatus(key)} className="rounded-lg px-3 py-2 text-sm capitalize" style={{ background: status === key ? 'var(--accent-primary)' : 'var(--bg-elevated)', color: status === key ? '#fff' : 'var(--text-secondary)' }}>
              {key}
            </button>
          ))}
        </div>
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
          {filtered.length === 0 ? (
            <div className="py-8 text-center text-sm" style={{ color: 'var(--text-secondary)' }}>No returns found</div>
          ) : filtered.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => { beginValidationRequest(predictionRequestId); setManuallySelectedId(item.id); setImagePreview(null) }}
              className="w-full rounded-xl border p-4 text-left transition-all"
              style={{
                background: selectedId === item.id ? 'var(--bg-elevated)' : 'var(--bg-card)',
                borderColor: selectedId === item.id ? 'var(--accent-primary)' : 'var(--border-color)',
                borderLeft: selectedId === item.id ? '3px solid var(--accent-primary)' : '3px solid transparent',
              }}
            >
              <div className="mb-2 flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="rounded-full bg-violet-600/20 p-2 text-violet-400"><Box size={16} /></div>
                  <div>
                    <div className="font-medium">{item.product_name}</div>
                    <div className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>{item.return_id}</div>
                  </div>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <DecisionBadge value={formatDecision(item.recommended_decision || item.status, false, item.confidence_score)} />
              </div>
            </button>
          ))}
        </div>
      </section>

      <section className="col-span-3 min-h-0 overflow-y-auto rounded-xl border p-5 max-lg:col-span-1 max-lg:h-[calc(100dvh-108px)]" style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}>
        {!selected ? (
          <div className="flex min-h-[700px] flex-col items-center justify-center text-center">
            <Box size={48} style={{ color: 'var(--text-muted)' }} />
            <h3 className="mt-4 text-xl font-semibold">{filtered.length ? 'Select a return to review' : 'No returns found'}</h3>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="border-b pb-4" style={{ borderColor: 'var(--border-color)' }}>
              <div className="mb-2 flex items-center gap-3">
                <h2 className="text-xl font-semibold">{selected.product_name}</h2>
                <DecisionBadge value={displayedDecision || selected.status} />
              </div>
              <div className="font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>{selected.return_id}</div>
            </div>

            <div>
              <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: 'var(--text-muted)' }}>Inspector Assessment</div>
              <div>
                <select
                  value={form.condition}
                  disabled={Boolean(predictionMeta || selected?.analyzed_at) || predictCondition.isPending}
                  onChange={(e) => {
                    setForm((p) => ({ ...p, condition: e.target.value }))
                    setAssessmentDirty(true)
                    setAnalysisResult(null)
                  }}
                  className="h-11 w-full rounded-lg border px-3"
                  style={{ background: 'var(--bg-sidebar)', borderColor: 'var(--border-color)' }}
                >
                  <option value="">Select condition</option>
                  {conditionOptions.map((option) => <option key={option}>{option}</option>)}
                </select>
              </div>
              <div className="mt-4">
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span>Condition Score</span>
                  <span className="rounded-full px-2 py-1" style={{ background: 'var(--bg-elevated)' }}>{form.condition_score}/100</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={form.condition_score}
                  disabled={Boolean(predictionMeta || selected?.analyzed_at) || predictCondition.isPending}
                  onChange={(e) => {
                    setForm((p) => ({ ...p, condition_score: Number(e.target.value) }))
                    setAssessmentDirty(true)
                    setAnalysisResult(null)
                  }}
                  className="w-full"
                />
                <div className="mt-2 text-xs" style={{ color: 'var(--text-secondary)' }}>{scoreHint}</div>
              </div>
              <div
                role="button"
                tabIndex={imageUploadDisabled ? -1 : 0}
                aria-disabled={imageUploadDisabled}
                aria-label="Upload product image"
                onClick={() => {
                  if (imageUploadDisabled) return
                  imageInputRef.current?.click()
                }}
                onKeyDown={(event) => {
                  if (imageUploadDisabled) return
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    imageInputRef.current?.click()
                  }
                }}
                onDragEnter={onImageDragEnter}
                onDragOver={onImageDragOver}
                onDragLeave={onImageDragLeave}
                onDrop={onImageDrop}
                className="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-4 py-8 text-center outline-none transition-colors"
                style={{
                  borderColor: isDraggingImage ? 'var(--accent-primary)' : 'var(--border-color)',
                  background: isDraggingImage ? 'color-mix(in srgb, var(--accent-primary) 12%, var(--bg-main))' : 'var(--bg-main)',
                  opacity: imageUploadDisabled ? 0.7 : 1,
                }}
              >
                <ImagePlus size={24} className="mb-2" />
                <div className="font-medium">{isDraggingImage ? 'Release to upload image' : 'Drop product image here'}</div>
                <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>or click to browse — model scores condition automatically</div>
                <input
                  ref={imageInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  disabled={imageUploadDisabled}
                  onChange={(e) => {
                    void onImageSelected(e.target.files?.[0] || null)
                    e.target.value = ''
                  }}
                />
                {selectedImageUrl ? (
                  <div className="mt-4 w-full max-w-[420px] overflow-hidden rounded-xl border pointer-events-none" style={{ borderColor: 'var(--border-color)' }}>
                    <img src={selectedImageUrl} alt={`${selected.product_name || 'Return item'} image`} className="h-[220px] w-full object-cover" />
                  </div>
                ) : null}
                {selected ? (
                  <div
                    className={`mt-3 rounded-lg border p-3 text-sm ${productValidation === 'MATCH' ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300' : 'border-red-500/30 bg-red-500/10 text-red-300'}`}
                    role={productValidation === 'MATCH' ? 'status' : 'alert'}
                  >
                    <p className="font-semibold">{productValidationMessage}</p>
                  </div>
                ) : null}
                {form.image ? <div className="mt-3 text-sm">{form.image.name}</div> : null}
              </div>
              {predictCondition.isPending ? (
                <div className="mt-3 flex items-center gap-2 text-sm" role="status" style={{ color: 'var(--text-secondary)' }}>
                  <LoaderCircle size={16} className="animate-spin" />
                  Assessing product condition from the selected image…
                </div>
              ) : null}
              {predictionMeta ? (
                <div className="mt-3 rounded-lg border p-3 text-sm" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-elevated)' }}>
                  <span className="font-medium">{predictionMeta.confidence == null ? 'Assessed condition' : 'Detected condition'}: {toAssessmentCondition(predictionMeta.condition) || predictionMeta.condition}</span>
                  <span className="ml-3">Score: {predictionMeta.condition_score}/100</span>
                  <span className="ml-3">Model confidence: {predictionMeta.confidence == null ? 'Unavailable' : `${Math.round(predictionMeta.confidence)}%`}</span>
                </div>
              ) : null}
              {imageError ? (
                <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-red-400" role="alert">
                  <span>{imageError}</span>
                  {form.image ? <button type="button" className="underline" disabled={predictCondition.isPending} onClick={() => requestConditionPrediction(form.image)}>Retry analysis</button> : null}
                </div>
              ) : null}
              <label className="mt-4 block text-sm font-medium" htmlFor="inspector-note">Inspector&apos;s Note <span className="text-red-400">*</span></label>
              <textarea
                id="inspector-note"
                rows="3"
                required
                value={form.notes}
                onChange={(e) => { setForm((p) => ({ ...p, notes: e.target.value })); setApprovalError('') }}
                placeholder={productValidation === 'MATCH' ? 'Enter the inspection findings' : 'Image validation is required before entering notes'}
                className="mt-2 w-full rounded-xl border p-3 outline-none"
                style={{ background: 'var(--bg-sidebar)', borderColor: 'var(--border-color)', opacity: productValidation === 'MATCH' ? 1 : 0.7 }}
                aria-invalid={Boolean(approvalError && !form.notes.trim())}
                disabled={productValidation !== 'MATCH' || predictCondition.isPending || analyze.isPending}
              />
              <button type="button" onClick={onAnalyze} disabled={analyze.isPending || predictCondition.isPending || !hasSuccessfulInference || productValidation !== 'MATCH'} className="mt-4 h-11 w-full rounded-lg font-medium text-white" style={{ background: 'var(--accent-primary)', opacity: analyze.isPending || predictCondition.isPending || !hasSuccessfulInference || productValidation !== 'MATCH' ? 0.7 : 1 }}>
                {analyze.isPending ? 'Analyzing...' : 'Analyze with AI'}
              </button>
              {(!hasSuccessfulInference || productValidation !== 'MATCH') && !predictCondition.isPending ? (
                <p className="mt-2 text-sm text-amber-400" role="alert">{analysisBlockedReason}</p>
              ) : null}
            </div>

            {selectedAnalysis?.recommended_decision ? (
              <div className="animate-slide-up space-y-4">
                <div className="flex items-center gap-3 rounded-xl p-4" style={{ background: 'var(--accent-light)', color: 'var(--text-primary)' }}>
                  <Sparkles size={20} style={{ color: 'var(--accent-primary)' }} />
                  <div>
                    <div className="font-semibold">AI Recommends: {displayedDecision.toUpperCase()}</div>
                    <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      Confidence {Math.round(selectedAnalysis.confidence_score || 0)}%
                    </div>
                    {needsManualReview ? (
                      <div className="mt-2 inline-flex rounded-full bg-amber-500/15 px-2 py-1 text-xs font-semibold text-amber-400">
                        Low confidence — manual review recommended
                      </div>
                    ) : null}
                    {selectedAnalysis.decision_reason ? (
                      <div className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                        {selectedAnalysis.decision_reason}
                      </div>
                    ) : null}
                  </div>
                </div>

                <div className="rounded-xl p-4" style={{ background: 'color-mix(in srgb, var(--info) 10%, var(--bg-card))' }}>
                  <div className="mb-2 font-semibold">AI Image Analysis</div>
                  <p className="mb-4 text-sm" style={{ color: 'var(--text-secondary)' }}>{selectedAnalysis.ai_description}</p>
                  <div className="grid grid-cols-3 gap-3 max-sm:grid-cols-1">
                    <Metric label="Confidence" value={`${Math.round(selectedAnalysis.confidence_score || 0)}%`} />
                    <Metric label="Demand Score" value={`${Math.round(selectedAnalysis.demand_score || 0)}%`} />
                    <Metric label="Sustainability" value={`${Math.round(selectedAnalysis.sustainability_score || 0)}%`} />
                  </div>
                </div>

                {selectedAnalysis.ai_score != null || selectedAnalysis.inspector_score != null || selectedAnalysis.final_score != null ? (
                  <div className="grid grid-cols-3 gap-3 max-sm:grid-cols-1">
                    <Metric label="AI Score" value={selectedAnalysis.ai_score == null ? '--' : `${Math.round(selectedAnalysis.ai_score)}/100`} />
                    <Metric label="Inspector Score" value={selectedAnalysis.inspector_score == null ? '--' : `${Math.round(selectedAnalysis.inspector_score)}/100`} />
                    <Metric label="Final Score" value={selectedAnalysis.final_score == null ? '--' : `${Math.round(selectedAnalysis.final_score)}/100`} />
                  </div>
                ) : null}

                <div className="grid grid-cols-2 gap-3 max-sm:grid-cols-1">
                  <MetricCard icon={<TrendingUp size={18} />} label="Market Demand" value={selectedAnalysis.market_demand_percent ? `${Math.round(selectedAnalysis.market_demand_percent)}%` : '--'} />
                  <MetricCard icon={<Leaf size={18} />} label="Eco Score" value={selectedAnalysis.eco_score ? `${Math.round(selectedAnalysis.eco_score)}%` : '--'} />
                </div>
              </div>
            ) : null}

            <div className="sticky bottom-0 flex gap-3 border-t pt-4" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-card)' }}>
              <button type="button" disabled={remove.isPending || approve.isPending || reject.isPending} onClick={() => { if (window.confirm(`Delete ${selected.product_name}?`)) remove.mutate(selected.id, { onSuccess: () => { setManuallySelectedId(null); refetch() } }) }} className="h-11 rounded-lg border px-4 font-medium" style={{ borderColor: '#ef4444', color: '#ef4444' }}>
                Delete
              </button>
              <button type="button" disabled={selected.status !== 'pending' || !assessmentReady || !(selectedAnalysis?.recommended_decision) || approve.isPending || reject.isPending || analyze.isPending || predictCondition.isPending} onClick={() => onFinalize('rejected')} className="h-11 flex-1 rounded-lg border font-medium" style={{ borderColor: '#ef4444', color: '#ef4444', opacity: selected.status !== 'pending' || !assessmentReady || approve.isPending || reject.isPending || analyze.isPending || predictCondition.isPending ? 0.5 : 1 }}>
                Reject
              </button>
              <button type="button" title={approvalBlockedReason || (approvalWarnings.length ? approvalWarnings.join(' ') : undefined)} disabled={Boolean(approvalBlockedReason) || !selectedAnalysis?.recommended_decision || approve.isPending || reject.isPending || analyze.isPending || predictCondition.isPending} onClick={() => onFinalize('approved')} className="h-11 flex-1 rounded-lg font-medium text-white" style={{ background: 'var(--accent-primary)', opacity: approvalBlockedReason || !selectedAnalysis?.recommended_decision || approve.isPending || reject.isPending || analyze.isPending || predictCondition.isPending ? 0.5 : 1 }}>
                {approve.isPending ? 'Approving...' : 'Approve Decision'}
              </button>
            </div>
            {approvalError ? <div className="text-right text-sm text-red-400" role="alert">{approvalError}</div> : null}
            {!assessmentReady ? <div className="text-right text-xs" style={{ color: 'var(--text-secondary)' }}>Run analysis for the current condition before approving or rejecting.</div> : null}
            {approvalBlockedReason ? <div className="text-right text-xs text-red-400" role="status">{approvalBlockedReason}</div> : null}
            {approvalWarnings.length ? (
              <div className="space-y-1 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-300" role="status">
                {approvalWarnings.map((warning) => <p key={warning}>{warning}</p>)}
              </div>
            ) : null}
          </div>
        )}
      </section>
    </div>
  )
}

function Metric({ label, value }) {
  return (
    <div className="rounded-xl border p-3" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-card)' }}>
      <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  )
}

function createAssessmentState(key, item) {
  const hasCondition = item?.condition && item.condition_score != null
  return {
    key,
    form: {
      ...defaultForm,
      condition: toAssessmentCondition(item?.condition) || '',
      condition_score: item?.condition_score ?? defaultForm.condition_score,
      notes: item?.notes || '',
    },
    scoreOverride: false,
    predictionMeta: hasCondition
      ? {
          condition: toAssessmentCondition(item.condition) || item.condition,
          condition_score: item.condition_score,
          confidence: item.condition_confidence,
          product_label: item.product_label,
          product_confidence: item.product_confidence,
          product_validation: item.product_validation,
          expected_product: item.expected_product,
        }
      : null,
    analysisResult: null,
    assessmentDirty: false,
    imageError: '',
    approvalError: '',
  }
}

function toAssessmentCondition(condition) {
  if (condition === 'Like New') return 'Good'
  if (condition === 'Poor') return 'Bad'
  return conditionOptions.includes(condition) ? condition : null
}

function getApprovalBlockedReason({
  selected,
  assessment,
  assessmentReady,
  notes,
  productValidation,
}) {
  if (!selected || selected.status !== 'pending') return 'Only pending returns can be approved.'
  if (!notes.trim()) return "Enter the Inspector's Note before approving."
  if (assessment?.notes_conflict || assessment?.recommended_decision === 'Manual Review') {
    return assessment?.decision_reason || 'Condition conflict: manual review is required before approval.'
  }
  if (productValidation !== 'MATCH') {
    return getProductValidationMessage(productValidation)
  }
  if (!assessmentReady || !assessment?.recommended_decision) return 'Analyze the current condition assessment before approving.'
  if (assessment.profit_estimate_error) return 'Approval is unavailable until the assessment is complete.'
  return ''
}

function getApprovalWarnings(selected, assessment, settings) {
  if (!selected || !assessment) return []
  if (selected.status === 'approved' && selected.approval_warnings?.length) {
    return selected.approval_warnings.filter((warning) => !isProfitEstimationWarning(warning))
  }
  if (!settings) return []

  const warnings = []
  const confidence = Number(assessment.confidence_score || 0)
  const demand = Number(assessment.demand_score || 0)
  if (confidence < settings.min_confidence) {
    warnings.push(`Low model confidence — manual review recommended. Confidence is ${Math.round(confidence)}% (threshold: ${settings.min_confidence}%).`)
  }
  if (demand < settings.min_demand_score) {
    warnings.push(`Demand score is ${Math.round(demand)}% (threshold: ${settings.min_demand_score}%); manual review recommended.`)
  }
  return warnings
}

function isProfitEstimationWarning(warning) {
  return /estimated (loss|profit)|unable to estimate profit|approval will continue/i.test(String(warning))
}

function formatDecision(decision, needsReview, confidence) {
  if (!decision) return decision
  if (decision === 'Manual Review') return 'Refurbish'
  if (decision === 'Recycle' && (needsReview || Number(confidence) < 60)) {
    return 'Refurbish (low confidence – review)'
  }
  return decision
}

function MetricCard({ icon, label, value }) {
  return (
    <div className="rounded-xl border p-4" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-main)' }}>
      <div className="mb-3 flex items-center gap-2" style={{ color: 'var(--accent-primary)' }}>{icon}<span className="text-sm font-medium">{label}</span></div>
      <div className="text-xl font-semibold">{value}</div>
    </div>
  )
}

function getReturnImageUrl(imagePath) {
  if (!imagePath) return null
  const fileName = String(imagePath).split(/[\\/]/).pop()
  if (!fileName) return null
  const apiBaseUrl = new URL(api.defaults.baseURL, window.location.origin)
  apiBaseUrl.pathname = apiBaseUrl.pathname.replace(/\/api\/?$/, '')
  return new URL(`/uploads/${encodeURIComponent(fileName)}`, apiBaseUrl).toString()
}
