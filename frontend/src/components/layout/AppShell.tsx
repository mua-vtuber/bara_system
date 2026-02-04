import { useState } from 'react'
import { Header } from './Header'
import { TabBar, type TabId } from './TabBar'
import { StatusBar } from './StatusBar'
import { ChatPage } from '@/components/chat/ChatPage'
import { ActivityPage } from '@/components/activity/ActivityPage'
import { InfoPage } from '@/components/info/InfoPage'
import { SettingsPage } from '@/components/settings/SettingsPage'
import { MissionsPage } from '@/components/missions/MissionsPage'
import { ApprovalQueue } from '@/components/approval/ApprovalQueue'

const TAB_CONTENT: Record<TabId, React.FC> = {
  chat: ChatPage,
  activity: ActivityPage,
  missions: MissionsPage,
  info: InfoPage,
  settings: SettingsPage,
}

export function AppShell() {
  const [activeTab, setActiveTab] = useState<TabId>('chat')

  const ActiveComponent = TAB_CONTENT[activeTab]

  return (
    <div className="flex h-screen flex-col bg-gray-100">
      <Header />
      <TabBar activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="flex-1 overflow-auto">
        <ActiveComponent />
      </main>
      <ApprovalQueue />
      <StatusBar />
    </div>
  )
}
