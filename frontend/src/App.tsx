import React, { useState, useEffect } from 'react';
import { AutomationMode } from './types';
import { api } from './api';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { DashboardView } from './views/DashboardView';
import { NewProjectView } from './views/NewProjectView';
import { ProjectsListView } from './views/ProjectsListView';
import { ProjectStudioView } from './views/ProjectStudioView';
import { PromptLibraryView } from './views/PromptLibraryView';
import { GeminiStudioView } from './views/GeminiStudioView';
import { FlowStudioView } from './views/FlowStudioView';
import { StitchStudioView } from './views/StitchStudioView';
import { GalleryView } from './views/GalleryView';
import { SettingsView } from './views/SettingsView';

export function App() {
  const [currentView, setCurrentView] = useState<string>('dashboard');
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [mode, setMode] = useState<AutomationMode>('auto');
  const [projectCount, setProjectCount] = useState<number>(0);

  // Status of services
  const [geminiStatus, setGeminiStatus] = useState<any>({ logged_in: false });
  const [flowStatus, setFlowStatus] = useState<any>({ logged_in: false });
  const [ffmpegStatus, setFFmpegStatus] = useState<any>({ installed: true });

  const refreshStatuses = async () => {
    try {
      const [gStatus, fStatus, ffStatus, projects] = await Promise.allSettled([
        api.getGeminiStatus(),
        api.getFlowStatus(),
        api.getFFmpegStatus(),
        api.listProjects()
      ]);

      if (gStatus.status === 'fulfilled') setGeminiStatus(gStatus.value);
      if (fStatus.status === 'fulfilled') setFlowStatus(fStatus.value);
      if (ffStatus.status === 'fulfilled') setFFmpegStatus(ffStatus.value);
      if (projects.status === 'fulfilled') {
        setProjectCount(projects.value.length);
        if (projects.value.length > 0) {
          setActiveProjectId((prev) => prev || projects.value[0].id);
        }
      }
    } catch (e) {
      console.error('Refresh status error:', e);
    }
  };

  useEffect(() => {
    refreshStatuses();
    const timer = setInterval(() => {
      refreshStatuses();
    }, 6000);
    return () => clearInterval(timer);
  }, []);

  const handleOpenProject = (id: string) => {
    setActiveProjectId(id);
    setCurrentView('studio');
  };

  const handleNewProject = () => {
    setCurrentView('new_project');
  };

  const handleProjectCreated = (newId: string) => {
    setActiveProjectId(newId);
    setCurrentView('studio');
    refreshStatuses();
  };

  return (
    <div className="min-h-screen bg-[#0a0c10] text-[#f1f5f9] flex flex-col font-sans selection:bg-pink-500/30">
      {/* Top Header */}
      <Header
        mode={mode}
        onModeChange={(newMode) => {
          setMode(newMode);
          api.updateSettings({ default_mode: newMode }).catch(() => {});
          if (newMode === 'manual') {
            setCurrentView('manual_studio');
          } else if (currentView === 'manual_studio') {
            setCurrentView('studio');
          }
        }}
        geminiStatus={geminiStatus}
        flowStatus={flowStatus}
        ffmpegStatus={ffmpegStatus}
        onRefreshStatus={refreshStatuses}
      />

      {/* Main Studio Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        <Sidebar
          currentView={currentView}
          onSelectView={(v) => {
            if (v === 'manual_studio') {
              setMode('manual');
              setCurrentView('manual_studio');
            } else {
              setCurrentView(v);
            }
          }}
          projectCount={projectCount}
        />

        {/* Central Viewport */}
        <main className="flex-1 overflow-y-auto">
          {currentView === 'dashboard' && (
            <DashboardView
              onNewProject={handleNewProject}
              onOpenProject={handleOpenProject}
              geminiStatus={geminiStatus}
              flowStatus={flowStatus}
              ffmpegStatus={ffmpegStatus}
            />
          )}

          {currentView === 'new_project' && (
            <NewProjectView
              onBack={() => setCurrentView('projects')}
              onProjectCreated={handleProjectCreated}
              defaultMode={mode}
            />
          )}

          {currentView === 'projects' && (
            <ProjectsListView
              onNewProject={handleNewProject}
              onOpenProject={handleOpenProject}
            />
          )}

          {(currentView === 'studio' || currentView === 'manual_studio') && (
            <ProjectStudioView
              projectId={activeProjectId}
              onBack={() => setCurrentView('projects')}
              geminiStatus={geminiStatus}
              flowStatus={flowStatus}
              ffmpegStatus={ffmpegStatus}
              onRefreshStatus={refreshStatuses}
              mode={mode}
              initialTab={currentView === 'manual_studio' || mode === 'manual' ? 'manual_flow' : 'character'}
              onProjectCreated={(newId) => {
                setActiveProjectId(newId);
                refreshStatuses();
              }}
            />
          )}

          {currentView === 'character_gallery' && (
            <GalleryView initialType="image" onOpenProject={handleOpenProject} />
          )}

          {currentView === 'video_gallery' && (
            <GalleryView initialType="video" onOpenProject={handleOpenProject} />
          )}

          {currentView === 'prompt_library' && (
            <PromptLibraryView />
          )}

          {currentView === 'gemini_studio' && (
            <GeminiStudioView status={geminiStatus} onRefresh={refreshStatuses} />
          )}

          {currentView === 'flow_studio' && (
            <FlowStudioView status={flowStatus} onRefresh={refreshStatuses} />
          )}

          {currentView === 'stitch_studio' && (
            <StitchStudioView />
          )}

          {currentView === 'settings' && (
            <SettingsView />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
