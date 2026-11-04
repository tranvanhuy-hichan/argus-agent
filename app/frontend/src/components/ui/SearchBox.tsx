import { Search } from 'lucide-react'
import { Input } from '@/components/ui/Form'

/** Ô tìm kiếm dùng chung; đặt ở hàng tab (prop `right` của Tabs) để mọi trang giống nhau. */
export function SearchBox({ value, onChange, placeholder, label }: { value: string; onChange: (v: string) => void; placeholder: string; label: string }) {
  return (
    <div className="relative w-full sm:w-96">
      <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted" />
      <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} aria-label={label} className="h-9 pl-9" />
    </div>
  )
}
