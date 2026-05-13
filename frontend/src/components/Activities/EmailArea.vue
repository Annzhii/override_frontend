<template>
  <div
    class="cursor-pointer flex flex-col rounded-md shadow bg-surface-cards px-3 py-1.5 text-base transition-all duration-300 ease-in-out"
  >
    <div
      class="-mb-0.5 flex items-center justify-between gap-2 truncate text-ink-gray-9"
    >
      <div class="flex items-center gap-2 truncate">
        <span>{{ activity.data.sender_full_name }}</span>
        <span class="sm:flex hidden text-sm text-ink-gray-5">
          {{ '<' + activity.data.sender + '>' }}
        </span>
        <Badge
          v-if="activity.communication_type == 'Automated Message'"
          :label="__('Notification')"
          variant="subtle"
          theme="green"
        />
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <Badge
          v-if="status.label"
          :label="__(status.label)"
          variant="subtle"
          :theme="status.color"
        />
        <Tooltip :text="formatDate(activity.communication_date)">
          <div class="text-sm text-ink-gray-5">
            {{ __(timeAgo(activity.communication_date)) }}
          </div>
        </Tooltip>
        <div class="flex gap-0.5">
          <Button
            :tooltip="__('Reply')"
            variant="ghost"
            class="text-ink-gray-7"
            :icon="ReplyIcon"
            @click="reply(activity.data)"
          />
          <Button
            :tooltip="__('Reply All')"
            variant="ghost"
            :icon="ReplyAllIcon"
            class="text-ink-gray-7"
            @click="reply(activity.data, true)"
          />
        </div>
      </div>
    </div>
    <div class="flex flex-col gap-1 text-base leading-5 text-ink-gray-8">
      <div>{{ activity.data.subject }}</div>
      <div>
        <span class="mr-1 text-ink-gray-5"> {{ __('To') }}: </span>
        <span>{{ activity.data.recipients }}</span>
        <span v-if="activity.data.cc">, </span>
        <span v-if="activity.data.cc" class="mr-1 text-ink-gray-5">
          {{ __('CC') }}:
        </span>
        <span v-if="activity.data.cc">{{ activity.data.cc }}</span>
        <span v-if="activity.data.bcc">, </span>
        <span v-if="activity.data.bcc" class="mr-1 text-ink-gray-5">
          {{ __('BCC') }}:
        </span>
        <span v-if="activity.data.bcc">{{ activity.data.bcc }}</span>
      </div>
    </div>
    <div class="border-0 border-t mt-3 mb-1 border-outline-gray-modals" />
    <EmailContent :content="activity.data.content" />
    <div v-if="activity.data?.attachments?.length" class="flex flex-wrap gap-2">
      <AttachmentItem
        v-for="a in activity.data.attachments"
        :key="a.file_url"
        :label="a.file_name"
        :url="a.file_url"
      />
    </div>
  </div>
</template>
<script setup>
import { nextTick } from 'vue'
import ReplyIcon from '@/components/Icons/ReplyIcon.vue'
import ReplyAllIcon from '@/components/Icons/ReplyAllIcon.vue'
import AttachmentItem from '@/components/AttachmentItem.vue'
import EmailContent from '@/components/Activities/EmailContent.vue'
import { Badge, Tooltip } from 'frappe-ui'
import { timeAgo, formatDate } from '@/utils'
import { computed } from 'vue'
import { usersStore } from '@/stores/users'
const { getUser } = usersStore()
const user = computed(() => getUser() || {})

const props = defineProps({
  activity: Object,
  emailBox: Object,
})

const extractEmail = (emailString) => {
  if (!emailString) return ''
  const match = emailString.match(/<(.+?)>/)
  return match ? match[1] : emailString.trim()
}
function normalizeForTiptap(html) {
  if (!html) return ''

  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')

  /**
   * unwrap node
   * <div><table></table></div>
   * =>
   * <table></table>
   */
  function unwrap(el) {
    while (el.firstChild) {
      el.parentNode.insertBefore(el.firstChild, el)
    }

    el.remove()
  }

  /**
   * div -> p
   */
  function convertDivToParagraph(div) {
    const p = doc.createElement('p')

    while (div.firstChild) {
      p.appendChild(div.firstChild)
    }

    div.replaceWith(p)
  }

  /**
   * 是否纯文本 block
   */
  function isTextBlock(el) {
    return !el.querySelector(
      'table,ul,ol,img,video,iframe'
    )
  }

  /**
   * 删除尾部空白 text node
   */
  function removeTrailingWhitespace(el) {
    while (
      el.lastChild &&
      el.lastChild.nodeType === Node.TEXT_NODE &&
      !el.lastChild.textContent
        .replace(/\u00A0/g, '')
        .trim()
    ) {
      el.lastChild.remove()
    }
  }

  /**
   * 删除尾部 br
   * <p>Hello<br></p>
   * =>
   * <p>Hello</p>
   */
  function removeTrailingBR(el) {

    while (true) {

      // 先删尾部 whitespace
      removeTrailingWhitespace(el)

      // 再删 br
      if (
        el.lastChild &&
        el.lastChild.nodeName === 'BR'
      ) {
        el.lastChild.remove()
        continue
      }

      break
    }
  }

  /**
   * 是否空 block
   */
  function isEmptyBlock(el) {

    const clone = el.cloneNode(true)

    clone.querySelectorAll('br').forEach(br => br.remove())

    const text = clone.textContent
      .replace(/\u00A0/g, '')
      .trim()

    return (
      !text &&
      !clone.querySelector(
        'img,table,iframe,video,ul,ol'
      )
    )
  }

  /**
   * unwrap section/article
   */
  doc
    .querySelectorAll('section,article')
    .forEach(unwrap)

  /**
   * normalize div
   */
  doc.querySelectorAll('div').forEach(div => {

    // 先删尾部 br
    removeTrailingBR(div)

    // 空 div -> p
    if (isEmptyBlock(div)) {
      const p = doc.createElement('p')
      div.replaceWith(p)
      return
    }

    // layout div
    if (
      div.children.length === 1 &&
      ['TABLE', 'UL', 'OL'].includes(
        div.firstElementChild.nodeName
      )
    ) {
      unwrap(div)
      return
    }

    // 纯文本 div -> p
    if (isTextBlock(div)) {
      convertDivToParagraph(div)
      return
    }

    // 混合结构 div
    unwrap(div)
  })

  /**
   * normalize p
   */
  doc.querySelectorAll('p').forEach(p => {

    // 删除尾部 br
    removeTrailingBR(p)

    // 空 p
    if (isEmptyBlock(p)) {
      p.innerHTML = ''
    }
  })

  /**
   * 删除无意义 whitespace text node
   */
  const walker = doc.createTreeWalker(
    doc.body,
    NodeFilter.SHOW_TEXT,
  )

  const removeNodes = []

  while (walker.nextNode()) {

    const node = walker.currentNode

    if (
      !node.textContent
        .replace(/\u00A0/g, '')
        .trim()
    ) {
      removeNodes.push(node)
    }
  }

  removeNodes.forEach(node => node.remove())

  /**
   * trim p 首尾换行/缩进
   * （因为 ProseMirror 是 white-space: pre-wrap）
   */
  doc.querySelectorAll('p').forEach(p => {

    if (
      p.childNodes.length === 1 &&
      p.firstChild.nodeType === Node.TEXT_NODE
    ) {
      p.textContent = p.textContent.trim()
    }

  })

  /**
   * collapse 连续空 p
   */
  let prevEmpty = false

  doc.querySelectorAll('p').forEach(p => {

    const empty =
      !p.textContent.trim() &&
      !p.querySelector('img')

    if (empty) {

      if (prevEmpty) {
        p.remove()
        return
      }

      prevEmpty = true
      return
    }

    prevEmpty = false
  })

  return doc.body.innerHTML
}

async function reply(email, reply_all = false) {
  function escapeHTML(str = '') {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
  }

  function normalizeEmails(value) {
    if (!value) return ''

    return value
      .split(/[\n,;]+/)
      .map((v) => escapeHTML(v.trim()))
      .filter(Boolean)
      .join(', ')
  }
  const from = normalizeEmails(email.sender)
  const to = normalizeEmails(email.recipients)
  const cc = normalizeEmails(email.cc)
  const subject = email.subject || ''
  const date = (email.communication_date || '').slice(0, 16)
  const replyHeader = [
    `<p>------------------ Original Message ------------------</p>`,
    `<p><strong>From:</strong> ${from}</p>`,
    `<p><strong>Date:</strong> ${date}</p>`,
    `<p><strong>To:</strong> ${to}</p>`,
    cc ? `<p><strong>Cc:</strong> ${cc}</p>` : '',
    `<p><strong>Subject:</strong> ${subject}</p>`
  ].join('')

  props.emailBox.show = true
  let editor = props.emailBox.editor
  let message = normalizeForTiptap(email.content)
  let recipients = email.recipients.split(',').map((r) => r.trim())
  if (email.sent_or_received === "Received") {
    editor.toEmails = [email.sender]
  } else if (email.sent_or_received === "Sent") {
    editor.toEmails = recipients
  }
  editor.cc = editor.bcc = false
  editor.ccEmails = []
  editor.bccEmails = []

  if (!email.subject.startsWith('Re:')) {
    editor.subject = `Re: ${email.subject}`
  } else {
    editor.subject = email.subject
  }

  if (reply_all) {
    let cc = email.cc?.split(',').map((r) => r.trim())
    let bcc = email.bcc?.split(',').map((r) => r.trim())

    if (email.sent_or_received ==="Received") {
      cc = cc || []
      cc = cc.filter((r) => extractEmail(r) !== user.value.email)
      const filteredRecipients = recipients.filter((r) => extractEmail(r) !== user.value.email)
      cc.push(...filteredRecipients)
    } else if (email.sent_or_received ==="Sent") {
      cc = cc || []
      cc.push(...[email.sender])
      cc = cc.filter((r) => r !== user.value.email)
    }

    editor.cc = cc ? true : false
    editor.bcc = bcc ? true : false

    editor.ccEmails = cc
    editor.bccEmails = bcc
  }

  let repliedMessage = `<blockquote>
  ${replyHeader}
  <p></p>
  ${message}
  </blockquote>`

  const hasContent = editor.editor.getText().trim().length > 0

  if (!hasContent) {
    // 没有内容：完整初始化回复格式
    editor.editor
      .chain()
      .insertContent('<p>.</p>')
      .updateAttributes('paragraph', { class: 'reply-to-content' })
      .insertContent(repliedMessage)
      .insertContentAt(0, { type: 'paragraph' })
      .focus('start')
      .run()
  } else {
    await nextTick()
    // 有内容（草稿）不改变现有格式
    editor.editor
      .chain()
      .focus('start')
      .run()
  }
}

const status = computed(() => {
  let _status = props.activity?.data?.delivery_status
  let indicator_color = 'red'
  if (['Sent', 'Clicked'].includes(_status)) {
    indicator_color = 'green'
  } else if (['Sending', 'Scheduled'].includes(_status)) {
    indicator_color = 'orange'
  } else if (['Opened', 'Read'].includes(_status)) {
    indicator_color = 'blue'
  } else if (_status == 'Error') {
    indicator_color = 'red'
  }
  return { label: _status, color: indicator_color }
})
</script>
