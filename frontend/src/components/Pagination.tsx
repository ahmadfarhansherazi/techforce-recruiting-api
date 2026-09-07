interface PaginationProps {
  total: number
  limit: number
  offset: number
  onOffsetChange: (offset: number) => void
}

export function Pagination({ total, limit, offset, onOffsetChange }: PaginationProps) {
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + limit, total)
  const canGoBack = offset > 0
  const canGoForward = offset + limit < total

  return (
    <div className="pagination">
      <button type="button" disabled={!canGoBack} onClick={() => onOffsetChange(Math.max(0, offset - limit))}>
        Previous
      </button>
      <span>
        {from}–{to} of {total}
      </span>
      <button type="button" disabled={!canGoForward} onClick={() => onOffsetChange(offset + limit)}>
        Next
      </button>
    </div>
  )
}
