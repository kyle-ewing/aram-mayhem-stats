import { useEffect, useMemo, useState } from 'react'
import {
  addMayhemAugment,
  getMayhemAugments,
  updateMayhemAugment,
} from '../api'
import RarityBadge from './RarityBadge'

const TIERS = ['Silver', 'Gold', 'Prismatic']
const EMPTY_FORM = { name: '', tier: 'Silver', id: '', notes: '' }

const TIER_ORDER = { Silver: 0, Gold: 1, Prismatic: 2 }

export default function AugmentManager() {
  const [augments, setAugments] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)

  const [form, setForm] = useState(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState(null)
  const [savedName, setSavedName] = useState(null)

  // Inline row editing: editingName holds the ORIGINAL name of the row being
  // edited (the key the backend looks up), so a rename still targets the right
  // record.
  const [editingName, setEditingName] = useState(null)
  const [editForm, setEditForm] = useState(EMPTY_FORM)
  const [editSaving, setEditSaving] = useState(false)
  const [editError, setEditError] = useState(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setLoadError(null)
    getMayhemAugments()
      .then((rows) => {
        if (active) setAugments(rows ?? [])
      })
      .catch((err) => {
        if (active) setLoadError(err.message || 'Could not load augments.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const sorted = useMemo(() => {
    return [...augments].sort((a, b) => {
      const t = (TIER_ORDER[a.tier] ?? 9) - (TIER_ORDER[b.tier] ?? 9)
      if (t !== 0) return t
      return a.name.localeCompare(b.name)
    })
  }, [augments])

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function onSubmit(e) {
    e.preventDefault()
    setFormError(null)
    setSavedName(null)

    const name = form.name.trim()
    if (!name) {
      setFormError('Name is required.')
      return
    }

    const entry = {
      name,
      tier: form.tier,
      id: form.id.trim() === '' ? null : Number(form.id),
      notes: form.notes.trim(),
    }
    if (entry.id !== null && !Number.isInteger(entry.id)) {
      setFormError('Id must be a whole number, or left blank.')
      return
    }

    setSubmitting(true)
    try {
      const record = await addMayhemAugment(entry)
      setAugments((prev) => [...prev, record])
      setSavedName(record.name)
      setForm({ ...EMPTY_FORM, tier: form.tier })
    }
    catch (err) {
      setFormError(err.message || 'Could not save augment.')
    }
    finally {
      setSubmitting(false)
    }
  }

  function startEdit(augment) {
    setEditError(null)
    setEditingName(augment.name)
    setEditForm({
      name: augment.name,
      tier: augment.tier,
      id: augment.id == null ? '' : String(augment.id),
      notes: augment.notes ?? '',
    })
  }

  function cancelEdit() {
    setEditingName(null)
    setEditError(null)
  }

  function updateEdit(field, value) {
    setEditForm((prev) => ({ ...prev, [field]: value }))
  }

  async function saveEdit() {
    setEditError(null)

    const name = editForm.name.trim()
    if (!name) {
      setEditError('Name is required.')
      return
    }

    const entry = {
      name,
      tier: editForm.tier,
      id: editForm.id.trim() === '' ? null : Number(editForm.id),
      notes: editForm.notes.trim(),
    }
    if (entry.id !== null && !Number.isInteger(entry.id)) {
      setEditError('Id must be a whole number, or left blank.')
      return
    }

    setEditSaving(true)
    try {
      const record = await updateMayhemAugment(editingName, entry)
      setAugments((prev) =>
        prev.map((a) => (a.name === editingName ? record : a)),
      )
      setEditingName(null)
    }
    catch (err) {
      setEditError(err.message || 'Could not save changes.')
    }
    finally {
      setEditSaving(false)
    }
  }

  return (
    <section className="augment-manager">
      <h2>Add a Mayhem augment</h2>
      <p className="subtitle">
        Record an augment as you see it in game. Saved entries are written to the
        curated Mayhem augment list on the server.
      </p>

      <form className="augment-form" onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="aug-name">Name</label>
          <input
            id="aug-name"
            type="text"
            value={form.name}
            onChange={(e) => update('name', e.target.value)}
            placeholder="e.g. Infernal Conduit"
            autoComplete="off"
          />
        </div>

        <div className="field">
          <label htmlFor="aug-tier">Tier</label>
          <select
            id="aug-tier"
            value={form.tier}
            onChange={(e) => update('tier', e.target.value)}
          >
            {TIERS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="aug-id">Id (optional)</label>
          <input
            id="aug-id"
            type="number"
            value={form.id}
            onChange={(e) => update('id', e.target.value)}
            placeholder="Community Dragon id"
          />
        </div>

        <div className="field field-wide">
          <label htmlFor="aug-notes">Notes (optional)</label>
          <textarea
            id="aug-notes"
            value={form.notes}
            onChange={(e) => update('notes', e.target.value)}
            rows={2}
          />
        </div>

        <div className="form-actions">
          <button type="submit" disabled={submitting}>
            {submitting ? 'Saving...' : 'Add augment'}
          </button>
          {savedName && (
            <span className="form-ok" role="status">
              Added "{savedName}".
            </span>
          )}
          {formError && (
            <span className="form-err" role="alert">
              {formError}
            </span>
          )}
        </div>
      </form>

      <h3>Current list ({augments.length})</h3>

      {loading && <p className="status">Loading augments...</p>}
      {loadError && !loading && (
        <p className="status error" role="alert">
          {loadError}
        </p>
      )}

      {!loading && !loadError && sorted.length === 0 && (
        <p className="empty">No augments recorded yet.</p>
      )}

      {!loading && !loadError && sorted.length > 0 && (
        <table className="augment-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Tier</th>
              <th>Id</th>
              <th>Notes</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {sorted.map((a) =>
              editingName === a.name ? (
                <tr key={a.name} className="editing">
                  <td>
                    <input
                      type="text"
                      value={editForm.name}
                      onChange={(e) => updateEdit('name', e.target.value)}
                      aria-label="Name"
                    />
                  </td>
                  <td>
                    <select
                      value={editForm.tier}
                      onChange={(e) => updateEdit('tier', e.target.value)}
                      aria-label="Tier"
                    >
                      {TIERS.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      type="number"
                      value={editForm.id}
                      onChange={(e) => updateEdit('id', e.target.value)}
                      aria-label="Id"
                      className="id-input"
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={editForm.notes}
                      onChange={(e) => updateEdit('notes', e.target.value)}
                      aria-label="Notes"
                    />
                  </td>
                  <td className="row-actions">
                    <button
                      type="button"
                      onClick={saveEdit}
                      disabled={editSaving}
                    >
                      {editSaving ? 'Saving...' : 'Save'}
                    </button>
                    <button
                      type="button"
                      className="link-button"
                      onClick={cancelEdit}
                      disabled={editSaving}
                    >
                      Cancel
                    </button>
                    {editError && (
                      <span className="form-err" role="alert">
                        {editError}
                      </span>
                    )}
                  </td>
                </tr>
              ) : (
                <tr key={a.name}>
                  <td>{a.name}</td>
                  <td>
                    <RarityBadge rarity={a.tier} />
                  </td>
                  <td>{a.id ?? ''}</td>
                  <td>{a.notes}</td>
                  <td className="row-actions">
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => startEdit(a)}
                      disabled={editingName !== null}
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      )}
    </section>
  )
}
