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

function cleanEmailHTML(html) {
  if (!html) return ''

  return html
    // ① 删除空 div 或只有 br 的 div（最关键）
    .replace(/<div[^>]*>\s*(<br\s*\/?>|&nbsp;|\s)*\s*<\/div>/gi, '')

    // ② 把 div（带内容）转成 p
    .replace(/<div[^>]*>/gi, '<p>')
    .replace(/<\/div>/gi, '</p>')

    // ③ 删除段落结尾的 <br>（避免生成空 p）
    .replace(/<br>\s*<\/p>/gi, '</p>')

    // ④ 删除“只有空白”的段落（重点）
    .replace(/<p>(&nbsp;|\s)*<\/p>/gi, '')

    // ⑤ 删除“只有 br 的段落”
    //.replace(/<p>\s*<br\s*\/?>\s*<\/p>/gi, '')

    // ⑥ 合并多余换行
    .replace(/(<br\s*\/?>\s*){2,}/gi, '<br>')

    // ⑦ 清理换行符
    .replace(/\n/g, '')

    .trim()
}

async function reply(email, reply_all = false) {
  props.emailBox.show = true
  let editor = props.emailBox.editor
  let message = cleanEmailHTML(email.content)
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

  let repliedMessage = `<blockquote>${message}</blockquote>`

  const hasContent = editor.editor.getText().trim().length > 0

  if (!hasContent) {
    // 没有内容：完整初始化回复格式
    editor.editor
      .chain()
      .insertContent('<p>.</p>')
      .updateAttributes('paragraph', { class: 'reply-to-content' })
      .insertContent(repliedMessage)
      .focus('all')
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
