import { ArrowLeft, ArrowRight, ImagePlus, Trash2 } from 'lucide-react'
import { type ChangeEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { deleteImage, updateImage, uploadImage } from '../../api'
import { adminErrorKey } from '../../errors'
import { useCatalogMutation } from '../../hooks'
import type { AdminImage, AdminVariant } from '../../types'
import { ConfirmDialog, ErrorNote } from '../ui'
import { inputClass } from '../inputClass'
import styles from './catalog.module.css'

const ACCEPT = 'image/jpeg,image/png,image/webp'

interface PhotosEditorProps {
  productId: number
  images: AdminImage[]
  variants: AdminVariant[]
}

function byPosition(images: AdminImage[]): AdminImage[] {
  return [...images].sort((a, b) => a.position - b.position || a.id - b.id)
}

/** The PATCHes that give each image its index as position, skipping those already right. */
function renumber(ordered: AdminImage[]): Promise<unknown>[] {
  return ordered
    .map((image, index) =>
      image.position === index ? null : updateImage(image.id, { position: index }),
    )
    .filter((call): call is Promise<AdminImage> => call !== null)
}

export function PhotosEditor({ productId, images, variants }: PhotosEditorProps) {
  const { t } = useTranslation()
  const ordered = byPosition(images)
  const [toDelete, setToDelete] = useState<AdminImage | null>(null)

  const upload = useCatalogMutation(async (files: File[]) => {
    // One by one, so positions follow the order the files were picked in.
    let position = ordered.length
    for (const file of files) await uploadImage(productId, file, position++)
  })
  const reorder = useCatalogMutation((next: AdminImage[]) => Promise.all(renumber(next)))
  const assign = useCatalogMutation(({ id, variantId }: { id: number; variantId: number | null }) =>
    updateImage(id, { variant_id: variantId }),
  )
  const remove = useCatalogMutation((id: number) => deleteImage(id))

  const busy = upload.isPending || reorder.isPending || assign.isPending || remove.isPending
  const failed = upload.error ?? reorder.error ?? assign.error
  const error = failed ? t(adminErrorKey(failed)) : null

  function pick(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? [])
    event.target.value = '' // picking the same file again should upload it again
    if (files.length > 0) upload.mutate(files)
  }

  function move(index: number, delta: -1 | 1) {
    const next = [...ordered]
    ;[next[index], next[index + delta]] = [next[index + delta], next[index]]
    reorder.mutate(next)
  }

  return (
    <div className={styles.section}>
      <div className={styles.photos}>
        {ordered.map((image, index) => (
          <div key={image.id} className={styles.photo}>
            <img src={image.url} alt="" className={styles.photoImage} />
            <select
              className={inputClass}
              aria-label={t('admin.catalog.photoVariant')}
              value={image.variant_id ?? ''}
              disabled={busy}
              onChange={(event) =>
                assign.mutate({
                  id: image.id,
                  variantId: event.target.value ? Number(event.target.value) : null,
                })
              }
            >
              <option value="">{t('admin.catalog.wholeProduct')}</option>
              {variants.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.sku}
                </option>
              ))}
            </select>
            <div className={styles.photoTools}>
              <button
                type="button"
                className={styles.tool}
                aria-label={t('admin.catalog.moveLeft')}
                disabled={busy || index === 0}
                onClick={() => move(index, -1)}
              >
                <ArrowLeft size={16} aria-hidden />
              </button>
              <button
                type="button"
                className={styles.tool}
                aria-label={t('admin.catalog.moveRight')}
                disabled={busy || index === ordered.length - 1}
                onClick={() => move(index, 1)}
              >
                <ArrowRight size={16} aria-hidden />
              </button>
              <button
                type="button"
                className={styles.tool}
                aria-label={t('admin.catalog.deletePhoto')}
                disabled={busy}
                onClick={() => setToDelete(image)}
              >
                <Trash2 size={16} aria-hidden />
              </button>
            </div>
          </div>
        ))}
        <label className={styles.upload}>
          <ImagePlus size={20} aria-hidden />
          {upload.isPending ? t('admin.catalog.uploading') : t('admin.catalog.addPhotos')}
          <input type="file" accept={ACCEPT} multiple disabled={busy} onChange={pick} />
        </label>
      </div>
      <p className={styles.muted}>{t('admin.catalog.photosHint')}</p>
      <ErrorNote message={error} />
      <ConfirmDialog
        open={toDelete !== null}
        title={t('admin.catalog.deletePhotoTitle')}
        confirmLabel={t('admin.common.delete')}
        busy={remove.isPending}
        error={remove.error ? t(adminErrorKey(remove.error)) : null}
        onCancel={() => {
          remove.reset()
          setToDelete(null)
        }}
        onConfirm={() =>
          toDelete && remove.mutate(toDelete.id, { onSuccess: () => setToDelete(null) })
        }
      />
    </div>
  )
}
