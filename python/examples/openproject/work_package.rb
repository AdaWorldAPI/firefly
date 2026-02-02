# Example Ruby model from OpenProject
# Used to demonstrate Firefly compilation

class WorkPackage < ApplicationRecord
  belongs_to :project
  belongs_to :type
  belongs_to :status
  belongs_to :author, class_name: 'User'
  belongs_to :assigned_to, class_name: 'Principal', optional: true

  has_many :time_entries, dependent: :destroy
  has_many :journals, as: :journable, dependent: :destroy
  has_many :attachments, as: :container, dependent: :destroy

  validates :subject, presence: true, length: { maximum: 255 }
  validates :project, presence: true
  validates :type, presence: true
  validates :status, presence: true
  validates :author, presence: true
  validates :priority, presence: true

  before_save :update_project_module
  before_create :set_default_status
  after_create :create_journal_entry
  after_update :notify_watchers
  before_destroy :check_deletability

  scope :visible, -> { where(visible: true) }
  scope :open, -> { joins(:status).where(statuses: { is_closed: false }) }
  scope :for_project, ->(project) { where(project_id: project.id) }
end
