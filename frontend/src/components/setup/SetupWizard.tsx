import { useState, useCallback } from 'react'
import { StepPassword } from './StepPassword'
import { StepSystemCheck } from './StepSystemCheck'
import { StepModelSelect } from './StepModelSelect'
import { StepBotName } from './StepBotName'
import { StepPlatforms } from './StepPlatforms'
import { StepBehavior } from './StepBehavior'
import { StepVoice } from './StepVoice'
import { StepComplete } from './StepComplete'
import clsx from 'clsx'

const STEPS = [
  '비밀번호',
  '시스템 확인',
  '모델 선택',
  '봇 설정',
  '플랫폼',
  '행동 설정',
  '음성',
  '완료',
] as const

interface SetupWizardProps {
  onComplete: () => void
}

export function SetupWizard({ onComplete }: SetupWizardProps) {
  const [currentStep, setCurrentStep] = useState(0)

  const goNext = useCallback(() => {
    setCurrentStep((prev) => Math.min(prev + 1, STEPS.length - 1))
  }, [])

  const renderStep = () => {
    switch (currentStep) {
      case 0:
        return <StepPassword onNext={goNext} />
      case 1:
        return <StepSystemCheck onNext={goNext} />
      case 2:
        return <StepModelSelect onNext={goNext} />
      case 3:
        return <StepBotName onNext={goNext} />
      case 4:
        return <StepPlatforms onNext={goNext} />
      case 5:
        return <StepBehavior onNext={goNext} />
      case 6:
        return <StepVoice onNext={goNext} />
      case 7:
        return <StepComplete onComplete={onComplete} />
      default:
        return null
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-100">
      <div className="w-full max-w-lg rounded-lg bg-white p-8 shadow-md">
        {/* Step indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            {STEPS.map((step, idx) => (
              <div key={step} className="flex items-center">
                <div
                  className={clsx(
                    'flex h-8 w-8 items-center justify-center rounded-full text-xs font-medium',
                    idx < currentStep
                      ? 'bg-blue-600 text-white'
                      : idx === currentStep
                        ? 'border-2 border-blue-600 text-blue-600'
                        : 'border border-gray-300 text-gray-400',
                  )}
                >
                  {idx < currentStep ? (
                    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  ) : (
                    idx + 1
                  )}
                </div>
                {idx < STEPS.length - 1 && (
                  <div
                    className={clsx(
                      'mx-1 h-0.5 w-6',
                      idx < currentStep ? 'bg-blue-600' : 'bg-gray-200',
                    )}
                  />
                )}
              </div>
            ))}
          </div>
          <p className="mt-2 text-center text-xs text-gray-500">
            {currentStep + 1} / {STEPS.length} - {STEPS[currentStep]}
          </p>
        </div>

        {/* Step content */}
        {renderStep()}
      </div>
    </div>
  )
}
